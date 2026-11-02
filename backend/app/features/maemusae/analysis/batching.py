"""분석 묶음 나누기와 근거 확인. DB·AI 를 모르는 순수 함수라 따로 테스트합니다.

묶음 (10/29 SoYoung 결정):
- 쪽 단위로만 나누고 쪽 중간을 자르지 않습니다. 같은 파일의 이어진 쪽은 순서대로 붙여 보내 쪽을 넘는 문장도 이어 읽힙니다
- 묶음이 바뀌는 곳에서 앞 묶음 마지막 쪽의 끝부분(overlap 글자)을 다음 묶음 앞에 "앞 쪽에서 이어짐"으로 겹쳐 넣습니다
- 쪽마다 [P12 · 요청서.pdf · 3쪽] 표시를 붙이고, AI 는 근거를 이 번호(P12)와 문장으로 답합니다

근거 확인: 공백·줄바꿈·마크다운 기호를 정리한 뒤 문장이 그 쪽 본문에 있는지 봅니다. 없으면 그 쪽 끝과
같은 파일 다음 쪽 앞을 이어 붙여 다시 찾고, 찾으면 끝 쪽을 함께 돌려줍니다(화면 3~4쪽).
"""

import re
from dataclasses import dataclass

WINDOW = 1000  # 쪽을 넘는 문장을 찾을 때 이어 붙이는 앞·뒤 글자 수


@dataclass(frozen=True)
class PageRef:
    id: int
    source_file_id: int
    seq: int
    filename: str  # 직접 쓴 글은 "직접 입력"
    location_label: str
    text: str


@dataclass(frozen=True)
class Batch:
    text: str  # AI 에 보낼 본문 (쪽 표시 포함)
    tags: tuple[str, ...]  # 이 묶음에 들어간 쪽 번호 (P1, P2…)


def tag_of(index: int) -> str:
    return f"P{index}"


def _header(tag: str, page: PageRef) -> str:
    return f"[{tag} · {page.filename} · {page.location_label}]"


def make_batches(pages: list[PageRef], *, limit: int, overlap: int) -> tuple[list[Batch], dict[str, PageRef]]:
    """쪽 목록(파일 순, 파일 안 seq 순) → 묶음 목록과 쪽 번호표. 쪽 하나가 limit 보다 길면 그 쪽만 한 묶음입니다."""
    by_tag = {tag_of(i): page for i, page in enumerate(pages, 1)}
    batches: list[Batch] = []
    parts: list[str] = []
    tags: list[str] = []
    size = 0
    prev: tuple[str, PageRef] | None = None  # 앞 묶음의 마지막 쪽

    for tag, page in by_tag.items():
        block = f"{_header(tag, page)}\n{page.text.strip()}"
        if parts and size + len(block) > limit:
            batches.append(Batch("\n\n".join(parts), tuple(tags)))
            parts, tags, size = [], [], 0
            # 앞 묶음 마지막 쪽이 같은 파일의 바로 앞 쪽이면 끝부분을 겹쳐 넣어 잘린 문장을 이어 읽게 합니다
            if prev and overlap > 0 and prev[1].source_file_id == page.source_file_id and prev[1].seq + 1 == page.seq:
                tail = prev[1].text.strip()[-overlap:]
                carried = f"[{prev[0]} · 앞 쪽에서 이어짐]\n…{tail}"
                parts.append(carried)
                tags.append(prev[0])
                size += len(carried)
        parts.append(block)
        tags.append(tag)
        size += len(block)
        prev = (tag, page)
    if parts:
        batches.append(Batch("\n\n".join(parts), tuple(tags)))
    return batches, by_tag


_MARKDOWN = re.compile(r"[*_`#>|~\[\]]")
_SPACES = re.compile(r"\s+")
_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "…": " "})


def normalize(value: str) -> str:
    """비교용: 따옴표 통일, 마크다운 기호 제거, 공백 하나로, 소문자"""
    value = _MARKDOWN.sub(" ", value.translate(_QUOTES))
    return _SPACES.sub(" ", value).strip().lower()


def locate(quote: str, page: PageRef, next_page: PageRef | None) -> tuple[bool, PageRef | None]:
    """(찾았는지, 끝 쪽). 그 쪽 안에서 찾으면 끝 쪽 없음, 다음 쪽까지 이어서 찾으면 다음 쪽"""
    needle = normalize(quote)
    if len(needle) < 2:
        return False, None
    if needle in normalize(page.text):
        return True, None
    if next_page and next_page.source_file_id == page.source_file_id and next_page.seq == page.seq + 1:
        joined = normalize(page.text[-WINDOW:]) + " " + normalize(next_page.text[:WINDOW])
        if needle in joined:
            return True, next_page
    return False, None

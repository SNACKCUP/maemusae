"""대·중·소분류(업무 영역) 이름 정리 (M4-2, 10/29 결정 F).

AI 가 묶음마다 따로 답하면 같은 영역을 '회원관리' / '회원 관리'처럼 다르게 쓰기 쉬워서, 띄어쓰기·대소문자만 다른 이름은
먼저 쓴 이름 하나로 맞춥니다. 그리고 이미 쓴 분류 목록을 다음 묶음의 AI 에게 같이 보내 같은 이름을 다시 쓰게 합니다.
뜻이 비슷한 다른 말(예: 회원 / 사용자)은 서버가 판단하지 않습니다 (사람이 화면에서 고침).
"""

import re
from collections.abc import Iterable

CATEGORY_MAX = 100
PROMPT_MAX_PATHS = 80  # 지시문에 넣을 기존 분류 수 (너무 길어지지 않게)
NONE_TEXT = "(없음)"

CategoryPath = tuple[str | None, str | None, str | None]

_SPACES = re.compile(r"\s+")


def clean(value: str | None) -> str | None:
    """앞뒤·겹친 공백 정리, 100자, 빈 값은 None"""
    text = _SPACES.sub(" ", value or "").strip()[:CATEGORY_MAX].strip()
    return text or None


def _key(value: str) -> str:
    return value.replace(" ", "").casefold()


class CategoryBook:
    """이 문서에서 쓴 분류 이름. 같은 이름(띄어쓰기·대소문자 무시)은 먼저 쓴 표기로 맞춤"""

    def __init__(self, paths: Iterable[CategoryPath] = ()):
        self._names: dict[str, str] = {}
        self._paths: dict[CategoryPath, None] = {}
        for path in paths:
            self.canon(path)

    def _name(self, value: str | None) -> str | None:
        value = clean(value)
        if value is None:
            return None
        return self._names.setdefault(_key(value), value)

    def canon(self, path: CategoryPath) -> CategoryPath:
        """정리한 (대, 중, 소). 대분류 없이 중·소분류만 있으면 위로 당김 (빈칸 없이 위에서부터 채움)"""
        names = [n for n in (self._name(v) for v in path) if n]
        result: CategoryPath = tuple(names + [None] * (3 - len(names)))  # type: ignore[assignment]
        if result[0]:
            self._paths.setdefault(result, None)
        return result

    def prompt_text(self) -> str:
        paths = list(self._paths)[:PROMPT_MAX_PATHS]
        return "\n".join("- " + " > ".join(p for p in path if p) for path in paths) or NONE_TEXT

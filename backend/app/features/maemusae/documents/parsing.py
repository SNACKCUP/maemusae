"""올린 파일 → 쪽(위치) 단위 마크다운. MarkItDown 으로 바꾸고, 형식마다 쪽 정보를 살려 나눕니다.

| 형식      | 나누는 단위                     | 위치 표시            |
| PDF       | 쪽 (한 쪽씩 잘라서 변환)         | 3쪽                  |
| PPTX      | 슬라이드                         | 슬라이드 4           |
| XLSX      | 시트                             | 시트 '요구사항'      |
| DOCX, MD  | 제목(#, ##). 제목이 없으면 글자 수 | 2. 결제 요구사항     |
| TXT       | 글자 수                          | 1부분                |

글자 수로 나눌 때는 한도 근처의 빈 줄(문단) → 문장 끝 → 줄바꿈 순서로 자를 곳을 찾아 문장 중간을 자르지 않습니다.
쪽 정보가 있는 형식(PDF·PPTX)은 쪽 그대로 둡니다. 쪽을 넘어가는 문장은 쓰는 쪽(M3)에서 이어 붙입니다.

MarkItDown 은 플러그인을 끄고 파일 바이트만 넘깁니다 (인터넷 주소·외부 프로그램을 부르지 않음).
본문과 파일 이름은 로그에 남기지 않습니다.
"""

import io
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PureWindowsPath

from app.features.maemusae.config import mms_settings
from app.features.maemusae.errors import (
    DocumentParseFailedError,
    DocumentTooLongError,
    UnsupportedFileTypeError,
)

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
# docx·pptx·xlsx 는 zip 이라 안에 이 파일이 있어야 진짜 그 형식입니다
_OFFICE_MARKER = {".docx": "word/document.xml", ".pptx": "ppt/presentation.xml", ".xlsx": "xl/workbook.xml"}
# 압축을 풀면 이보다 커지는 zip 은 받지 않습니다 (작은 파일로 메모리를 채우는 압축 폭탄 방지)
_MAX_UNZIPPED_BYTES = 200 * 1024 * 1024
_LABEL_MAX = 200

_HEADING = re.compile(r"^#{1,2}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
_SLIDE = re.compile(r"^<!-- Slide number: (\d+) -->$", re.MULTILINE)
_SHEET = re.compile(r"^## (.+)$", re.MULTILINE)
_SENTENCE_END = re.compile(r"[.?!。](?=\s)|\n")


@dataclass(frozen=True)
class Page:
    location_label: str
    text: str
    page_no: int | None = None


@dataclass(frozen=True)
class Converted:
    content_type: str
    pages: list[Page]


def clean_filename(filename: str | None) -> str:
    """경로를 떼고 제어 문자를 지운 파일 이름 (255자까지)."""
    name = PureWindowsPath(filename or "").name  # C:\a\b.pdf, ../b.pdf 모두 b.pdf
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[-255:] or "file"


def convert(data: bytes, filename: str) -> Converted:
    """파일 하나를 쪽 목록으로. 형식이 다르면 415, 읽을 글자가 없으면 422, 너무 길면 422."""
    ext = PureWindowsPath(filename).suffix.lower()
    if ext not in CONTENT_TYPES:
        raise UnsupportedFileTypeError()
    _check_signature(data, ext)
    try:
        pages = _CONVERTERS[ext](data)
    except (DocumentTooLongError, DocumentParseFailedError, UnsupportedFileTypeError):
        raise
    except Exception as e:  # 깨진 파일, 암호 걸린 PDF 등. 원문 메시지에 본문이 섞일 수 있어 넘기지 않음
        raise DocumentParseFailedError() from e
    pages = [p for p in pages if p.text]
    if not pages:
        raise DocumentParseFailedError()  # 스캔한 이미지 PDF 처럼 글자가 없음
    _check_length(sum(len(p.text) for p in pages))
    return Converted(CONTENT_TYPES[ext], pages)


def text_page(text: str) -> Page:
    """직접 쓴 글은 나누지 않고 1행."""
    text = _normalize(text)
    _check_length(len(text))
    return Page("직접 입력", text)


# ---- 형식 확인 ----


def _check_signature(data: bytes, ext: str) -> None:
    if ext == ".pdf":
        ok = data.startswith(b"%PDF-")
    elif ext in _OFFICE_MARKER:
        ok = _is_office_zip(data, _OFFICE_MARKER[ext])
    else:
        ok = b"\x00" not in data  # 글 파일에 NUL 이 있으면 실제로는 다른 형식
    if not ok:
        raise UnsupportedFileTypeError()


def _is_office_zip(data: bytes, marker: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile:
        return False
    if sum(info.file_size for info in infos) > _MAX_UNZIPPED_BYTES:
        raise DocumentParseFailedError()
    return any(info.filename == marker for info in infos)


def _check_length(chars: int) -> None:
    if chars > mms_settings.mms_source_max_chars:
        raise DocumentTooLongError(mms_settings.mms_source_max_chars)


# ---- 변환 ----


@lru_cache
def _markitdown():
    from markitdown import MarkItDown

    return MarkItDown(enable_plugins=False)


def _to_markdown(data: bytes, ext: str, charset: str | None = None) -> str:
    from markitdown import StreamInfo

    result = _markitdown().convert_stream(io.BytesIO(data), stream_info=StreamInfo(extension=ext, charset=charset))
    return _normalize(result.markdown)


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _pdf(data: bytes) -> list[Page]:
    import pypdfium2 as pdfium

    source = pdfium.PdfDocument(data)
    pages, total = [], 0
    try:
        for index in range(len(source)):
            one = pdfium.PdfDocument.new()
            try:
                one.import_pages(source, [index])
                buffer = io.BytesIO()
                one.save(buffer)
            finally:
                one.close()
            text = _to_markdown(buffer.getvalue(), ".pdf")
            total += len(text)
            _check_length(total)  # 아주 긴 PDF 는 끝까지 바꾸기 전에 멈춤
            pages.append(Page(f"{index + 1}쪽", text, page_no=index + 1))
    finally:
        source.close()
    return pages


def _pptx(data: bytes) -> list[Page]:
    markdown = _to_markdown(data, ".pptx")
    marks = list(_SLIDE.finditer(markdown))
    pages = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(markdown)
        number = int(mark.group(1))
        pages.append(Page(f"슬라이드 {number}", markdown[mark.end() : end].strip(), page_no=number))
    return pages


def _xlsx(data: bytes) -> list[Page]:
    markdown = _to_markdown(data, ".xlsx")
    marks = list(_SHEET.finditer(markdown))
    pages = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(markdown)
        pages += _chunked(f"시트 '{mark.group(1).strip()}'", markdown[mark.end() : end])
    return pages


def _docx(data: bytes) -> list[Page]:
    return _by_headings(_to_markdown(data, ".docx"))


def _md(data: bytes) -> list[Page]:
    return _by_headings(_decode(data))


def _txt(data: bytes) -> list[Page]:
    parts = split_text(_decode(data), mms_settings.mms_page_max_chars)
    return [Page(f"{i}부분", part) for i, part in enumerate(parts, 1)]


def _decode(data: bytes) -> str:
    """UTF-8, 안 되면 CP949 (한글 윈도우 메모장)."""
    for charset in ("utf-8-sig", "cp949"):
        try:
            return _normalize(data.decode(charset))
        except UnicodeDecodeError:
            continue
    raise DocumentParseFailedError()


_CONVERTERS = {".pdf": _pdf, ".pptx": _pptx, ".xlsx": _xlsx, ".docx": _docx, ".md": _md, ".txt": _txt}


# ---- 나누기 ----


def _by_headings(markdown: str) -> list[Page]:
    """# · ## 제목마다 한 조각. 제목이 없으면 글자 수로."""
    marks = list(_HEADING.finditer(markdown))
    if not marks:
        parts = split_text(markdown, mms_settings.mms_page_max_chars)
        return [Page(f"{i}부분", part) for i, part in enumerate(parts, 1)]
    pages = _chunked("시작 부분", markdown[: marks[0].start()])
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(markdown)
        pages += _chunked(mark.group(1).strip(), markdown[mark.start() : end])
    return pages


def _chunked(label: str, text: str) -> list[Page]:
    """한 위치가 한도보다 길면 '라벨 (1)', '라벨 (2)' 로 나눔."""
    parts = split_text(text.strip(), mms_settings.mms_page_max_chars)
    base = label[: _LABEL_MAX - 10]
    if len(parts) == 1:
        return [Page(base, parts[0])]
    return [Page(f"{base} ({i})", part) for i, part in enumerate(parts, 1)]


def split_text(text: str, limit: int) -> list[str]:
    """limit 글자 이하 조각으로. 빈 줄 → 문장 끝·줄바꿈 → (그래도 없으면) limit 위치 순서로 자를 곳을 찾습니다."""
    parts, rest = [], text.strip()
    while len(rest) > limit:
        window = rest[:limit]
        floor = limit // 2  # 너무 앞에서 자르면 조각이 잘게 쪼개지므로 뒤쪽 절반에서만 찾음
        cut = window.rfind("\n\n", floor)
        if cut == -1:
            ends = [m.end() for m in _SENTENCE_END.finditer(window, floor)]
            cut = ends[-1] if ends else limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts.append(rest)
    return [p for p in parts if p]

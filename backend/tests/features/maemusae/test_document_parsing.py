"""파일 → 쪽 단위 마크다운 (documents/parsing.py). API 를 거치지 않고 변환 규칙만 봅니다."""

import io
import zipfile

import pytest

from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents import parsing
from app.features.maemusae.errors import (
    DocumentParseFailedError,
    DocumentTooLongError,
    UnsupportedFileTypeError,
)
from tests.features.maemusae import samples


def _labels(converted) -> list[str]:
    return [p.location_label for p in converted.pages]


def test_pdf_is_split_per_page_with_page_numbers():
    converted = parsing.convert(samples.pdf(["Login with email.", "", "Pay by card."]), "req.pdf")
    assert converted.content_type == "application/pdf"
    # 글자 없는 2쪽은 빠지고, 쪽 번호는 원본 그대로
    assert [(p.page_no, p.location_label, p.text) for p in converted.pages] == [
        (1, "1쪽", "Login with email."),
        (3, "3쪽", "Pay by card."),
    ]


def test_pptx_is_split_per_slide():
    converted = parsing.convert(samples.pptx([("개요", "쇼핑몰 리뉴얼"), ("결제", "카드 결제 지원")]), "deck.pptx")
    assert _labels(converted) == ["슬라이드 1", "슬라이드 2"]
    assert [p.page_no for p in converted.pages] == [1, 2]
    assert "카드 결제 지원" in converted.pages[1].text
    assert "Slide number" not in converted.pages[1].text


def test_xlsx_is_split_per_sheet_as_markdown_table():
    data = samples.xlsx({"요구사항": [["ID", "내용"], [1, "로그인"]], "일정": [["단계", "날짜"], ["오픈", "12월"]]})
    converted = parsing.convert(data, "list.xlsx")
    assert _labels(converted) == ["시트 '요구사항'", "시트 '일정'"]
    assert "| 1 | 로그인 |" in converted.pages[0].text
    assert all(p.page_no is None for p in converted.pages)


def test_docx_is_split_by_headings():
    data = samples.docx(["머리말 문단", "# 1. 개요", "쇼핑몰을 새로 만든다.", "# 2. 결제 요구사항", "카드 결제를 지원한다."])
    converted = parsing.convert(data, "spec.docx")
    assert _labels(converted) == ["시작 부분", "1. 개요", "2. 결제 요구사항"]
    assert converted.pages[2].text.startswith("# 2. 결제 요구사항")
    assert "카드 결제를 지원한다." in converted.pages[2].text


def test_txt_without_headings_is_split_by_length_at_sentence_end(monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_page_max_chars", 60)
    sentence = "회원은 이메일로 가입할 수 있어야 한다. "  # 23자
    converted = parsing.convert((sentence * 6).encode(), "memo.txt")
    assert _labels(converted) == ["1부분", "2부분", "3부분"]
    for page in converted.pages:
        assert len(page.text) <= 60
        assert page.text.endswith("한다.")  # 문장 중간에서 자르지 않음


def test_txt_cp949_is_decoded():
    converted = parsing.convert("고객 요청 메모".encode("cp949"), "memo.txt")
    assert converted.pages[0].text == "고객 요청 메모"


def test_md_uses_headings():
    converted = parsing.convert("# 목표\n빠른 결제\n## 범위\n모바일".encode(), "note.md")
    assert _labels(converted) == ["목표", "범위"]


def test_split_text_prefers_paragraph_then_sentence_then_hard_cut():
    assert parsing.split_text("가나다라.\n\n마바사아자차카", 12) == ["가나다라.", "마바사아자차카"]
    assert parsing.split_text("가나다라마. 바사아자", 8) == ["가나다라마.", "바사아자"]
    assert parsing.split_text("가" * 10, 4) == ["가가가가", "가가가가", "가가"]


def test_long_section_gets_numbered_labels(monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_page_max_chars", 40)
    body = "결제는 카드로 한다. " * 6
    converted = parsing.convert(f"# 결제\n{body}".encode(), "a.md")
    assert _labels(converted)[:2] == ["결제 (1)", "결제 (2)"]


@pytest.mark.parametrize(
    ("data", "name"),
    [
        (b"hello", "a.hwp"),  # 지원 안 하는 확장자
        (b"not a pdf", "a.pdf"),  # 확장자만 PDF
        (samples.pdf(["x"]), "a.docx"),  # PDF 를 docx 로 이름만 바꿈
        (samples.xlsx({"a": [[1]]}), "a.docx"),  # zip 이지만 Word 가 아님
        (b"\x00\x01binary", "a.txt"),
    ],
)
def test_wrong_type_is_415(data, name):
    with pytest.raises(UnsupportedFileTypeError):
        parsing.convert(data, name)


def test_broken_or_textless_file_is_422():
    with pytest.raises(DocumentParseFailedError):
        parsing.convert(samples.pdf(["", ""]), "scan.pdf")  # 스캔 PDF 처럼 글자가 없음
    with pytest.raises(DocumentParseFailedError):
        parsing.convert(b"%PDF-1.4 broken", "broken.pdf")


def test_zip_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(parsing, "_MAX_UNZIPPED_BYTES", 1000)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "a" * 5000)
    with pytest.raises(DocumentParseFailedError):
        parsing.convert(buffer.getvalue(), "bomb.docx")


def test_too_long_is_422(monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_source_max_chars", 20)
    with pytest.raises(DocumentTooLongError):
        parsing.convert(samples.pdf(["Page one is long enough", "two"]), "long.pdf")
    with pytest.raises(DocumentTooLongError):
        parsing.text_page("가" * 21)


def test_clean_filename():
    assert parsing.clean_filename("C:\\Users\\me\\요청서.pdf") == "요청서.pdf"
    assert parsing.clean_filename("../../etc/passwd.txt") == "passwd.txt"
    assert parsing.clean_filename("a\x00b\n.pdf") == "ab.pdf"
    assert parsing.clean_filename(None) == "file"

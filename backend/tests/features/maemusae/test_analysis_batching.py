"""분석 묶음 나누기·근거 확인 (DB·AI 없이 도는 순수 함수)"""

from app.features.maemusae.analysis.batching import (
    PageRef,
    locate,
    make_batches,
    normalize,
)


def _page(id_: int, text: str, *, file_id: int = 1, seq: int | None = None) -> PageRef:
    return PageRef(id=id_, source_file_id=file_id, seq=seq or id_, filename="요청서.pdf", location_label=f"{seq or id_}쪽", text=text)


def test_small_document_is_one_batch_with_page_tags():
    batches, by_tag = make_batches([_page(1, "회원가입"), _page(2, "결제")], limit=1000, overlap=10)
    assert len(batches) == 1
    assert batches[0].tags == ("P1", "P2")
    assert "[P1 · 요청서.pdf · 1쪽]\n회원가입" in batches[0].text
    assert by_tag["P2"].id == 2


def test_splits_only_on_page_boundaries_and_carries_overlap():
    pages = [_page(1, "가" * 50 + "끝문장"), _page(2, "나" * 50), _page(3, "다" * 50)]
    batches, _ = make_batches(pages, limit=80, overlap=5)
    assert len(batches) == 3
    assert batches[0].text.count("[P") == 1  # 쪽 중간을 자르지 않음
    # 다음 묶음 앞에 앞 쪽 끝 5자를 "앞 쪽에서 이어짐"으로 겹쳐 넣음
    assert batches[1].text.startswith("[P1 · 앞 쪽에서 이어짐]\n…가가끝문장")
    assert batches[1].tags == ("P1", "P2")


def test_no_overlap_between_different_files_or_non_adjacent_pages():
    pages = [_page(1, "가" * 50, file_id=1), _page(2, "나" * 50, file_id=2, seq=1)]
    batches, _ = make_batches(pages, limit=60, overlap=5)
    assert len(batches) == 2
    assert "이어짐" not in batches[1].text


def test_normalize_ignores_spacing_markdown_and_quotes():
    assert normalize("**회원**은  “이메일”로\n가입") == normalize('회원 은 "이메일"로 가입')


def test_locate_in_page_across_pages_and_missing():
    first, second = _page(1, "회원은 이메일로"), _page(2, "가입한다. 결제는 카드")
    assert locate("이메일로", first, second) == (True, None)
    assert locate("회원은 이메일로 가입한다", first, second) == (True, second)  # 3~4쪽
    assert locate("지어낸 문장", first, second) == (False, None)
    assert locate("회원은 이메일로 가입한다", first, _page(3, "가입한다.", seq=5)) == (False, None)  # 이어진 쪽이 아님
    assert locate(" ", first, second) == (False, None)

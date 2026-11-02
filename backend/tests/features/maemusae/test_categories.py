"""매무새 대·중·소분류(업무 영역, M4-2): AI 가 채우고 같은 이름은 한 표기로, 다시 분류는 빈 분류만 채움,
사람이 고치기·지우기·직접 추가, 대분류 필터, 분류 목록, 버전·확정 기록과 Excel"""

import io
import logging
from contextlib import nullcontext

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.features.maemusae.analysis import runner
from app.features.maemusae.analysis.categories import CategoryBook, clean
from app.features.maemusae.analysis.models import Requirement
from app.features.maemusae.config import mms_settings
from app.users.models import User

PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}


@pytest.fixture(autouse=True)
def _app_logs_visible():
    # app 로거는 propagate=False 라서 caplog 가 받도록 테스트 동안만 켭니다 (하네스 pytest-app-logging)
    logger = logging.getLogger("app")
    logger.propagate = True
    yield
    logger.propagate = False


@pytest.fixture(autouse=True)
def _runner_uses_test_session(db, monkeypatch):
    monkeypatch.setattr(runner, "open_session", lambda: nullcontext(db))


@pytest.fixture
def owner(db, make_user, login):
    if db.scalar(select(User).where(User.login_id == "owner01")) is None:
        make_user("owner01", name="owner01 이름")
    return login("owner01")


@pytest.fixture
def docs_url(client, owner):
    project = client.post(PROJECTS, json=PROJECT, headers=owner).json()
    [document] = client.get(f"{PROJECTS}/{project['id']}/documents", headers=owner).json()
    return f"{PROJECTS}/{project['id']}/documents/{document['id']}"


def _req(name, quote, category=(None, None, None)):
    major, middle, minor = category
    return {
        "name": name, "description": f"{name} 설명", "kind": "FUNCTIONAL", "priority": "HIGH", "question": None,
        "category_major": major, "category_middle": middle, "category_minor": minor,
        "evidence": [{"page": "P1", "quote": quote}],
    }


def _rows(db, url) -> list[Requirement]:
    doc_id = int(url.rsplit("/", 1)[1])
    stmt = select(Requirement).where(Requirement.document_id == doc_id).order_by(Requirement.seq)
    return list(db.scalars(stmt.execution_options(populate_existing=True)))


def _paths(db, url) -> list[tuple]:
    return [(r.category_major, r.category_middle, r.category_minor) for r in _rows(db, url)]


def _prompt(fake_llm, index=-1) -> str:
    return "\n".join(str(m.content) for m in fake_llm.calls[index])


@pytest.fixture
def analyzed(client, owner, docs_url, fake_llm):
    """REQ-001 회원 관리 > 로그인 > 소셜 로그인, REQ-002 분류 없음"""
    assert client.post(f"{docs_url}/sources", data={"text": "카카오로 로그인한다. 카드로 결제한다."}, headers=owner).status_code == 201
    fake_llm.responses = [{
        "requirements": [
            _req("카카오 로그인", "카카오로 로그인한다", ("회원 관리", "로그인", "소셜 로그인")),
            _req("카드 결제", "카드로 결제한다"),
        ]
    }]
    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202
    fake_llm.calls.clear()
    return {r["code"]: r for r in client.get(f"{docs_url}/requirements", headers=owner).json()["items"]}


# ---- 이름 정리 ----


def test_category_book_keeps_first_spelling_and_fills_from_top():
    assert clean("  회원   관리 ") == "회원 관리"
    assert clean("   ") is None
    assert clean("가" * 150) == "가" * 100
    book = CategoryBook([("회원 관리", "로그인", None)])
    assert book.canon(("회원관리", "로그인", "소셜")) == ("회원 관리", "로그인", "소셜")  # 띄어쓰기만 다르면 먼저 쓴 표기
    assert book.canon(("API", None, None)) == ("API", None, None)
    assert book.canon(("api", "", None)) == ("API", None, None)  # 대소문자도
    assert book.canon((None, "결제", None)) == ("결제", None, None)  # 위가 비면 당겨 올림
    assert book.prompt_text().splitlines() == ["- 회원 관리 > 로그인", "- 회원 관리 > 로그인 > 소셜", "- API", "- 결제"]
    assert CategoryBook().prompt_text() == "(없음)"


# ---- AI 분석 ----


def test_analysis_saves_categories_and_reuses_names_across_batches(client, db, owner, docs_url, fake_llm, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_batch_chars", 40)
    monkeypatch.setattr(mms_settings, "mms_batch_overlap_chars", 0)
    client.post(f"{docs_url}/sources", data={"text": "카카오로 로그인한다. 아이디로도 로그인한다."}, headers=owner)
    client.post(f"{docs_url}/sources", data={"text": "카드로 결제한다. 주문 내역을 본다."}, headers=owner)
    fake_llm.responses = [
        {"requirements": [_req("카카오 로그인", "카카오로 로그인한다", ("회원 관리", "로그인", "소셜 로그인"))]},
        {"requirements": [
            _req("카드 결제", "카드로 결제한다", ("주문", "결제", None)),
            _req("아이디 로그인", "카드로 결제한다", ("회원관리", " 로그인 ", "아이디 로그인")),
        ]},
        {"groups": []},
    ]
    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202
    assert len(fake_llm.calls) == 3  # 묶음 2번 + 합치기

    assert "이미 쓴 분류:\n(없음)" in _prompt(fake_llm, 0)
    assert "- 회원 관리 > 로그인 > 소셜 로그인" in _prompt(fake_llm, 1)  # 앞 묶음 분류를 다음 묶음에 보냄
    assert _paths(db, docs_url) == [
        ("회원 관리", "로그인", "소셜 로그인"),
        ("주문", "결제", None),
        ("회원 관리", "로그인", "아이디 로그인"),  # '회원관리' → 먼저 쓴 '회원 관리'
    ]


def test_merged_candidate_takes_category_of_the_other_when_missing(client, db, owner, docs_url, fake_llm, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_batch_chars", 40)
    monkeypatch.setattr(mms_settings, "mms_batch_overlap_chars", 0)
    client.post(f"{docs_url}/sources", data={"text": "카카오로 로그인한다. 아이디로도 로그인한다."}, headers=owner)
    client.post(f"{docs_url}/sources", data={"text": "카드로 결제한다. 주문 내역을 본다."}, headers=owner)
    fake_llm.responses = [
        {"requirements": [_req("카카오 로그인", "카카오로 로그인한다")]},
        {"requirements": [_req("소셜 로그인", "카드로 결제한다", ("회원 관리", "로그인", None))]},
        {"groups": [[1, 2]]},
    ]
    client.post(f"{docs_url}/analyze", json={}, headers=owner)
    assert _paths(db, docs_url) == [("회원 관리", "로그인", None)]


# ---- 다시 분류 ----


def test_refine_fills_only_empty_categories(client, db, owner, docs_url, analyzed, fake_llm):
    for code in ("REQ-001", "REQ-002"):
        client.put(f"{docs_url}/requirements/{analyzed[code]['id']}/notes/DESCRIPTION", json={"text": "확인"}, headers=owner)
    fake_llm.responses = [{
        "updates": [
            {"ref": "R1", "category_major": "다른 영역", "category_middle": "바꾸기"},  # 이미 분류가 있음 → 무시
            {"ref": "R2", "category_major": "주문", "category_middle": "결제"},
        ]
    }]
    assert client.post(f"{docs_url}/refine", json={}, headers=owner).status_code == 202
    prompt = _prompt(fake_llm)
    assert "분류: 회원 관리 > 로그인 > 소셜 로그인" in prompt and "분류: (없음)" in prompt
    assert "이미 쓴 분류:\n- 회원 관리 > 로그인 > 소셜 로그인" in prompt
    assert _paths(db, docs_url) == [("회원 관리", "로그인", "소셜 로그인"), ("주문", "결제", None)]
    second = _rows(db, docs_url)[1]
    assert second.version == 2


# ---- 검토 API ----


def test_people_set_clear_and_add_categories(client, db, owner, docs_url, analyzed):
    login, pay = analyzed["REQ-001"], analyzed["REQ-002"]
    assert (login["category_major"], login["category_middle"], login["category_minor"]) == ("회원 관리", "로그인", "소셜 로그인")
    assert pay["category_major"] is None

    response = client.patch(
        f"{docs_url}/requirements/{pay['id']}",
        json={"version": 1, "category_major": "  주문 ", "category_middle": "결제"},
        headers=owner,
    )
    assert response.status_code == 200, response.text
    assert (response.json()["category_major"], response.json()["version"]) == ("주문", 2)
    response = client.patch(
        f"{docs_url}/requirements/{login['id']}", json={"version": 1, "category_minor": ""}, headers=owner
    )
    assert response.json()["category_minor"] is None  # 빈 글자 = 지우기
    too_long = client.patch(f"{docs_url}/requirements/{login['id']}", json={"version": 2, "category_major": "가" * 101}, headers=owner)
    assert too_long.status_code == 422

    bulk = client.patch(
        f"{docs_url}/requirements",
        json={"items": [{"id": login["id"], "version": 2, "category_major": "회원"}, {"id": pay["id"], "version": 2}]},
        headers=owner,
    )
    assert [i["category_major"] for i in bulk.json()] == ["회원", "주문"]

    created = client.post(
        f"{docs_url}/requirements",
        json={"name": "관리자 통계", "kind": "FUNCTIONAL", "priority": "LOW", "category_major": "관리자", "category_middle": " "},
        headers=owner,
    ).json()
    assert (created["category_major"], created["category_middle"]) == ("관리자", None)
    detail = client.get(f"{docs_url}/requirements/{created['id']}", headers=owner).json()
    assert detail["category_major"] == "관리자"


def test_filter_by_major_and_list_categories(client, owner, docs_url, analyzed):
    client.patch(f"{docs_url}/requirements/{analyzed['REQ-002']['id']}", json={"version": 1, "category_major": "주문"}, headers=owner)
    page = client.get(f"{docs_url}/requirements", params={"category_major": "주문"}, headers=owner).json()
    assert [i["code"] for i in page["items"]] == ["REQ-002"]

    categories = client.get(f"{docs_url}/categories", headers=owner).json()
    assert categories == [
        {"major": "주문", "middle": None, "minor": None, "count": 1},
        {"major": "회원 관리", "middle": "로그인", "minor": "소셜 로그인", "count": 1},
    ]


def test_versions_confirm_and_excel_carry_categories(client, owner, docs_url, analyzed):
    saved = client.post(f"{docs_url}/versions", headers=owner).json()
    items = client.get(f"{docs_url}/versions/{saved['id']}", headers=owner).json()["items"]
    assert [(i["code"], i["category_major"]) for i in items] == [("REQ-001", "회원 관리"), ("REQ-002", None)]

    confirmed = client.post(f"{docs_url}/confirm", headers=owner).json()
    content = client.get(f"{docs_url}/versions/{confirmed['version_id']}/excel", headers=owner).content
    sheet = load_workbook(io.BytesIO(content)).active
    assert [c.value for c in sheet[10][:4]] == ["REQ-001", "회원 관리", "로그인", "소셜 로그인"]
    assert [c.value for c in sheet[11][:2]] == ["REQ-002", None]  # 분류 없는 후보는 아래

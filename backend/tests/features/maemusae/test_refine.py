"""매무새 다시 분류 (M3-3): 입력 반영(이름 없이 "입력 1, 입력 2"), 충돌 입력 → 질문, 질문 답 → 확인 필요 풀기,
새 파일 반영(기존과 같으면 근거만 더하고 새 내용은 다음 번호), 사람 수정 우선, 막는 경우, 실패, 로그"""

import logging
from contextlib import nullcontext

import pytest
from sqlalchemy import select, update

from app.features.maemusae.analysis import runner
from app.features.maemusae.analysis.models import (
    AnalysisRun,
    Requirement,
    RequirementSource,
)
from app.features.maemusae.documents.models import SourceFile
from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.features.maemusae.review.models import RequirementNote
from app.llm.errors import LLMTimeoutError
from app.users.models import User

PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}
FIRST_TEXT = "회원은 이메일로 가입한다. 결제는 카드로 한다."
SECRET_NOTE = "간편결제도 꼭 넣어 주세요"


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
def headers(db, make_user, login):
    def _headers(login_id: str, *, admin: bool = False) -> dict[str, str]:
        if db.scalar(select(User).where(User.login_id == login_id)) is None:
            make_user(login_id, admin=admin, name=f"{login_id} 이름")
        return login(login_id)

    return _headers


@pytest.fixture
def owner(headers):
    return headers("owner01")


@pytest.fixture
def docs_url(client, owner):
    project = client.post(PROJECTS, json=PROJECT, headers=owner).json()
    [document] = client.get(f"{PROJECTS}/{project['id']}/documents", headers=owner).json()
    return f"{PROJECTS}/{project['id']}/documents/{document['id']}"


@pytest.fixture
def member(db, headers, docs_url):
    hdrs = headers("member01")
    user = db.scalar(select(User).where(User.login_id == "member01"))
    db.add(ProjectMember(project_id=int(docs_url.split("/")[4]), user_id=user.id, role=MEMBER))
    db.commit()
    return hdrs


def _doc_id(url: str) -> int:
    return int(url.rsplit("/", 1)[1])


def _req(name, quote, *, question=None):
    return {
        "name": name, "description": f"{name} 설명", "kind": "FUNCTIONAL", "priority": "HIGH",
        "question": question, "evidence": [{"page": "P1", "quote": quote}],
    }


@pytest.fixture
def analyzed(client, owner, docs_url, fake_llm):
    """분석이 끝난 문서: REQ-001 회원가입, REQ-002 결제(AI 질문 있음)"""
    assert client.post(f"{docs_url}/sources", data={"text": FIRST_TEXT}, headers=owner).status_code == 201
    fake_llm.responses = [
        {"requirements": [_req("회원가입", "이메일로 가입한다"), _req("결제", "결제는 카드로 한다", question="간편결제도 되나요?")]}
    ]
    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202
    fake_llm.calls.clear()
    return {r["code"]: r for r in client.get(f"{docs_url}/requirements", headers=owner).json()["items"]}


def _refine(client, url, hdrs, **body):
    return client.post(f"{url}/refine", json=body, headers=hdrs)


def _requirement(db, requirement_id) -> Requirement:
    return db.scalar(select(Requirement).where(Requirement.id == requirement_id).execution_options(populate_existing=True))


def _note(client, url, hdrs, requirement_id, field, text):
    response = client.put(f"{url}/requirements/{requirement_id}/notes/{field}", json={"text": text}, headers=hdrs)
    assert response.status_code == 200, response.text


def _prompt_text(fake_llm) -> str:
    return "\n".join(m.content for m in fake_llm.calls[-1])


# ---- 입력 반영 ----


def test_notes_are_applied_without_author_names(client, db, owner, member, docs_url, analyzed, fake_llm):
    payment = analyzed["REQ-002"]
    _note(client, docs_url, owner, payment["id"], "DESCRIPTION", SECRET_NOTE)
    _note(client, docs_url, member, payment["id"], "DESCRIPTION", "카카오페이만 우선")
    fake_llm.responses = [
        {"updates": [{"ref": "R1", "description": "카드와 간편결제로 결제한다", "priority": "MEDIUM"}]}
    ]

    response = _refine(client, docs_url, owner)
    assert response.status_code == 202
    prompt = _prompt_text(fake_llm)
    assert "입력 1 (설명 의견): " + SECRET_NOTE in prompt and "입력 2 (설명 의견): 카카오페이만 우선" in prompt
    assert "owner01" not in prompt and "member01" not in prompt  # 이름은 AI 에 보내지 않음
    assert "REQ-001" not in prompt  # 입력이 없는 후보는 보내지 않음
    assert len(fake_llm.calls) == 1  # 새 파일이 없으면 추출·맞춰 보기 없음

    requirement = _requirement(db, payment["id"])
    assert (requirement.seq, requirement.description, requirement.priority, requirement.version) == (
        2, "카드와 간편결제로 결제한다", "MEDIUM", 2,
    )
    run = db.get(AnalysisRun, response.json()["run_id"])
    assert (run.run_type, run.status, run.done_steps, run.total_steps) == ("REFINE", "SUCCEEDED", 1, 1)
    notes = client.get(f"{docs_url}/notes", headers=owner).json()
    assert [n["applied"] for n in notes] == [True, True]
    assert client.get(docs_url, headers=owner).json()["status"] == "READY"


def test_answer_clears_question_and_conflict_leaves_question(client, db, owner, member, docs_url, analyzed, fake_llm):
    signup, payment = analyzed["REQ-001"], analyzed["REQ-002"]
    _note(client, docs_url, owner, payment["id"], "ANSWER", "네, 간편결제도 돼야 해요")
    _note(client, docs_url, owner, signup["id"], "DESCRIPTION", "가입 3초 안에")
    _note(client, docs_url, member, signup["id"], "DESCRIPTION", "가입 5초 안에")
    question = "입력 1은 3초, 입력 2는 5초라고 했어요. 어느 쪽이 맞나요?"
    fake_llm.responses = [
        {
            "updates": [
                {"ref": "R1", "question": question},
                {"ref": "R2", "clear_question": True, "answer": "간편결제도 지원"},
                {"ref": "R9", "name": "없는 번호표"},  # 보낸 적 없는 번호표는 버림
            ]
        }
    ]
    assert _refine(client, docs_url, owner).status_code == 202
    prompt = _prompt_text(fake_llm)
    assert "AI 질문: 간편결제도 되나요?" in prompt and "입력 1 (질문 답)" in prompt

    signup_row, payment_row = _requirement(db, signup["id"]), _requirement(db, payment["id"])
    assert (signup_row.name, signup_row.ai_question) == ("회원가입", question)
    assert (payment_row.ai_question, payment_row.ai_answer) == (None, "간편결제도 지원")
    items = {r["code"]: r for r in client.get(f"{docs_url}/requirements", headers=owner).json()["items"]}
    assert (items["REQ-001"]["needs_answer"], items["REQ-002"]["needs_answer"]) == (True, False)


def test_invalid_codes_from_ai_are_ignored(client, db, owner, docs_url, analyzed, fake_llm):
    _note(client, docs_url, owner, analyzed["REQ-001"]["id"], "DESCRIPTION", "급해요")
    fake_llm.responses = [{"updates": [{"ref": "R1", "kind": "URGENT", "priority": "높음"}]}]
    assert _refine(client, docs_url, owner).status_code == 202
    row = _requirement(db, analyzed["REQ-001"]["id"])
    assert (row.kind, row.priority, row.version) == ("FUNCTIONAL", "HIGH", 1)  # 그대로 (처음 분석처럼 기본값을 넣지 않음)
    assert client.get(f"{docs_url}/notes", headers=owner).json()[0]["applied"] is True  # AI 가 본 입력은 반영됨


# ---- 새 파일 반영 ----


def test_new_file_adds_evidence_to_same_requirement_and_new_number(client, db, owner, docs_url, analyzed, fake_llm):
    response = client.post(
        f"{docs_url}/sources", data={"text": "이메일로 가입한다. 카카오로 로그인한다."}, headers=owner
    )
    new_source_id = response.json()["id"]
    fake_llm.responses = [
        {"requirements": [_req("이메일 회원가입", "이메일로 가입한다"), _req("카카오 로그인", "카카오로 로그인한다")]},
        {"groups": [[1, 3]]},  # 1 = 기존 REQ-001, 3 = 새 후보 '이메일 회원가입'
    ]
    run_id = _refine(client, docs_url, owner).json()["run_id"]

    extract_prompt = "\n".join(m.content for m in fake_llm.calls[0])
    assert "카카오로 로그인한다" in extract_prompt and "결제는 카드로 한다" not in extract_prompt  # 새 파일만 읽음
    match_prompt = _prompt_text(fake_llm)
    assert "(기존 REQ-001) 회원가입" in match_prompt and "3. 이메일 회원가입" in match_prompt

    rows = db.scalars(
        select(Requirement).where(Requirement.document_id == _doc_id(docs_url)).order_by(Requirement.seq)
    ).all()
    assert [(r.seq, r.name) for r in rows] == [(1, "회원가입"), (2, "결제"), (3, "카카오 로그인")]
    signup_sources = db.scalars(
        select(RequirementSource).where(RequirementSource.requirement_id == rows[0].id).order_by(RequirementSource.sort_order)
    ).all()
    assert [(s.sort_order, s.verified) for s in signup_sources] == [(1, True), (2, True)]
    new_source = db.get(SourceFile, new_source_id)
    db.refresh(new_source)
    assert new_source.analysis_run_id == run_id
    run = db.get(AnalysisRun, run_id)
    assert (run.status, run.done_steps, run.total_steps) == ("SUCCEEDED", 2, 2)  # 추출 1 + 맞춰 보기 1


# ---- 사람 수정 우선 ----


def test_human_edit_during_refine_wins(client, db, owner, docs_url, analyzed, fake_llm, monkeypatch, caplog):
    signup = analyzed["REQ-001"]
    _note(client, docs_url, owner, signup["id"], "DESCRIPTION", "소셜 가입도")
    original = runner._ask_refine

    def ask_then_human_edits(*args):
        result = original(*args)
        # AI 가 답하는 사이 사람이 같은 후보를 고침
        db.execute(update(Requirement).where(Requirement.id == signup["id"]).values(name="사람이 고침", version=2))
        db.commit()
        return result

    monkeypatch.setattr(runner, "_ask_refine", ask_then_human_edits)
    fake_llm.responses = [{"updates": [{"ref": "R1", "name": "AI 가 고침"}]}]
    with caplog.at_level(logging.INFO, logger="app"):
        assert _refine(client, docs_url, owner).status_code == 202
    assert _requirement(db, signup["id"]).name == "사람이 고침"
    assert client.get(f"{docs_url}/notes", headers=owner).json()[0]["applied"] is False  # 다음 분류로 남김
    assert "skipped=1" in caplog.text


# ---- 막는 경우·실패 ----


def test_refine_guards(client, db, headers, owner, docs_url, fake_llm, monkeypatch):
    client.post(f"{docs_url}/sources", data={"text": FIRST_TEXT}, headers=owner)
    response = _refine(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (400, "REFINE_NEEDS_REQUIREMENTS")

    fake_llm.responses = [{"requirements": [_req("회원가입", "이메일로 가입한다")]}]
    client.post(f"{docs_url}/analyze", json={}, headers=owner)
    response = _refine(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (400, "REFINE_NOTHING_NEW")

    master = headers("master01", admin=True)
    assert _refine(client, docs_url, master).json()["code"] == "PROJECT_MEMBER_REQUIRED"
    assert _refine(client, docs_url, headers("outsider01")).status_code == 404

    client.post(f"{docs_url}/sources", data={"text": "추가 자료"}, headers=owner)
    monkeypatch.setattr(runner, "run_refine", lambda run_id: None)  # 분류가 계속 도는 상태로 둠
    assert _refine(client, docs_url, owner).status_code == 202
    assert client.get(f"{docs_url}/analysis", headers=owner).json()["run_type"] == "REFINE"
    response = _refine(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (409, "DOCUMENT_BUSY")


def test_llm_error_keeps_everything_and_logs_no_content(client, db, owner, docs_url, analyzed, fake_llm, caplog):
    payment = analyzed["REQ-002"]
    _note(client, docs_url, owner, payment["id"], "DESCRIPTION", SECRET_NOTE)
    fake_llm.responses = [LLMTimeoutError("LLM_TIMEOUT", "늦음")]
    with caplog.at_level(logging.INFO, logger="app"):
        run_id = _refine(client, docs_url, owner, prompt="비밀 지시").json()["run_id"]
    run = db.get(AnalysisRun, run_id)
    db.refresh(run)
    assert (run.status, run.error_code) == ("FAILED", "LLM_TIMEOUT")
    assert client.get(docs_url, headers=owner).json()["status"] == "READY"  # 기존 후보는 그대로 씀
    assert _requirement(db, payment["id"]).version == 1
    assert db.scalar(select(RequirementNote.applied_run_id)) is None
    assert SECRET_NOTE not in caplog.text and "비밀 지시" not in caplog.text

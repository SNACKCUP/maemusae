"""매무새 AI 분석 (M3-1): 시작 202 → 뒤에서 분석 → 진행률·후보·근거, 크기별 방식, 실패·멈춤 정리, 권한, 로그"""

import logging
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.features.maemusae.analysis import runner
from app.features.maemusae.analysis.models import (
    AnalysisRun,
    Requirement,
    RequirementSource,
)
from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.features.maemusae.review.models import RequirementNote
from app.llm.errors import LLMTimeoutError
from app.users.models import User
from tests.features.maemusae import samples

PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}
SECRET_TEXT = "회원은 이메일로 가입한다. 결제는 카드로 한다."


@pytest.fixture(autouse=True)
def _app_logs_visible():
    # app 로거는 propagate=False 라서 caplog 가 받도록 테스트 동안만 켭니다 (하네스 pytest-app-logging)
    logger = logging.getLogger("app")
    logger.propagate = True
    yield
    logger.propagate = False


@pytest.fixture(autouse=True)
def _runner_uses_test_session(db, monkeypatch):
    # 뒤에서 도는 분석이 새 세션 대신 테스트 세션을 쓰게 함 (TestClient 는 응답 뒤 바로 백그라운드 작업을 실행)
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


def _doc_id(url: str) -> int:
    return int(url.rsplit("/", 1)[1])


def _add_text(client, url, hdrs, text=SECRET_TEXT):
    response = client.post(f"{url}/sources", data={"text": text}, headers=hdrs)
    assert response.status_code == 201, response.text


def _req(name, *, page="P1", quote="이메일로 가입한다", kind="FUNCTIONAL", priority="HIGH", question=None):
    return {
        "name": name,
        "description": f"{name} 설명",
        "kind": kind,
        "priority": priority,
        "question": question,
        "evidence": [{"page": page, "quote": quote}] if quote else [],
    }


def _analyze(client, url, hdrs, **body):
    return client.post(f"{url}/analyze", json=body, headers=hdrs)


def _requirements(db, url) -> list[Requirement]:
    return list(
        db.scalars(
            select(Requirement)
            .where(Requirement.document_id == _doc_id(url), Requirement.deleted_at.is_(None))
            .order_by(Requirement.seq)
        )
    )


def _sources(db, requirement: Requirement) -> list[RequirementSource]:
    return list(
        db.scalars(
            select(RequirementSource)
            .where(RequirementSource.requirement_id == requirement.id)
            .order_by(RequirementSource.sort_order)
        )
    )


# ---- 작은 문서: AI 1번 ----


def test_small_document_runs_once_and_saves_candidates(client, db, owner, docs_url, fake_llm):
    _add_text(client, docs_url, owner)
    fake_llm.responses = [
        {"requirements": [_req("이메일 회원가입"), _req("카드 결제", quote="카드로 한다", kind="NONE", priority="??")]}
    ]

    response = _analyze(client, docs_url, owner, prompt="결제를 꼼꼼히")
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    assert len(fake_llm.calls) == 1  # 묶음 하나라 합치기 없음
    sent = "\n".join(str(m.content) for m in fake_llm.calls[0])
    assert "[P1 · 직접 입력 · 직접 입력]" in sent
    assert "결제를 꼼꼼히" in sent
    assert "FUNCTIONAL(기능)" in sent and "MEDIUM(보통)" in sent  # 공통코드에서 읽은 목록
    assert "owner01 이름" not in sent  # 올린 사람 이름은 보내지 않음

    progress = client.get(f"{docs_url}/analysis", headers=owner).json()
    assert progress["run_id"] == run_id
    assert progress["status"] == "SUCCEEDED"
    assert (progress["done_steps"], progress["total_steps"]) == (1, 1)
    assert client.get(docs_url, headers=owner).json()["status"] == "READY"

    first, second = _requirements(db, docs_url)
    assert (first.seq, first.name, first.kind, first.priority, first.is_manual) == (1, "이메일 회원가입", "FUNCTIONAL", "HIGH", False)
    assert (first.kind_defaulted, first.priority_defaulted) == (False, False)
    # 목록에 없는 코드는 첫 구분·보통으로 넣고 "확인 필요" 표시
    assert (second.kind, second.priority) == ("FUNCTIONAL", "MEDIUM")
    assert (second.kind_defaulted, second.priority_defaulted) == (True, True)
    [evidence] = _sources(db, first)
    assert evidence.verified is True and evidence.end_source_page_id is None
    source = db.scalar(select(SourceFile).where(SourceFile.document_id == _doc_id(docs_url)))
    db.refresh(source)
    assert source.analysis_run_id == run_id


def test_evidence_made_up_or_unknown_page(client, db, owner, docs_url, fake_llm):
    _add_text(client, docs_url, owner)
    fake_llm.responses = [
        {
            "requirements": [
                {
                    **_req("회원가입", quote="문서에 없는 지어낸 문장"),
                    "evidence": [
                        {"page": "P1", "quote": "문서에 없는 지어낸 문장"},
                        {"page": "P9", "quote": "이메일로 가입한다"},  # 없는 쪽 번호 → 버림
                        {"page": "1", "quote": "카드로 한다"},  # 번호만 써도 P1 로 읽음
                    ],
                }
            ]
        }
    ]
    assert _analyze(client, docs_url, owner).status_code == 202
    [requirement] = _requirements(db, docs_url)
    assert [(s.quote, s.verified) for s in _sources(db, requirement)] == [
        ("문서에 없는 지어낸 문장", False),
        ("카드로 한다", True),
    ]


# ---- 보통 문서: 묶음마다 뽑고 합치기 ----


def test_multiple_batches_overlap_dedupe_and_cross_page_quote(
    client, db, owner, docs_url, fake_llm, private_storage, monkeypatch
):
    monkeypatch.setattr(mms_settings, "mms_batch_chars", 40)
    pdf = samples.pdf(["Members sign up with", "email address only.", "Pay by card."])
    response = client.post(
        f"{docs_url}/sources", files={"file": ("request.pdf", pdf, "application/pdf")}, headers=owner
    )
    assert response.status_code == 201, response.text
    fake_llm.responses = [
        {"requirements": [_req("Email signup", quote="sign up with email address", page="P1")]},
        {"requirements": [_req("Signup by email", quote="email address only", page="P2", question="소셜 가입도?")]},
        {"requirements": [_req("Card payment", quote="Pay by card", page="P3")]},
        {"groups": [[1, 2], [3, 99]]},  # 1·2 는 같은 요구사항, 없는 번호는 무시
    ]

    assert _analyze(client, docs_url, owner).status_code == 202

    assert len(fake_llm.calls) == 4  # 묶음 3번 + 합치기 1번
    second_batch = "\n".join(str(m.content) for m in fake_llm.calls[1])
    assert "[P1 · 앞 쪽에서 이어짐]" in second_batch  # 묶음 경계 겹침
    dedupe = "\n".join(str(m.content) for m in fake_llm.calls[3])
    assert "1. Email signup" in dedupe and "Members sign up" not in dedupe  # 이름·설명만, 본문은 안 보냄

    progress = client.get(f"{docs_url}/analysis", headers=owner).json()
    assert (progress["done_steps"], progress["total_steps"]) == (4, 4)

    merged, card = _requirements(db, docs_url)
    assert (merged.seq, merged.name, merged.ai_question) == (1, "Email signup", "소셜 가입도?")
    assert (card.seq, card.name) == (2, "Card payment")
    cross, single = _sources(db, merged)  # 합친 후보는 근거를 모두 남김
    pages = {p.seq: p.id for p in db.scalars(select(SourcePage))}
    assert (cross.verified, cross.source_page_id, cross.end_source_page_id) == (True, pages[1], pages[2])  # 1~2쪽
    assert (single.verified, single.end_source_page_id) == (True, None)


def test_too_large_document_is_rejected_before_starting(client, db, owner, docs_url, fake_llm, monkeypatch):
    _add_text(client, docs_url, owner, "가" * 100)
    _add_text(client, docs_url, owner, "나" * 100)
    monkeypatch.setattr(mms_settings, "mms_batch_chars", 120)
    monkeypatch.setattr(mms_settings, "mms_analyze_max_batches", 1)

    response = _analyze(client, docs_url, owner)
    assert response.status_code == 422
    assert response.json()["code"] == "DOCUMENT_TOO_LARGE_TO_ANALYZE"
    assert "필요 없는 파일을 빼고" in response.json()["detail"]
    assert fake_llm.calls == []
    assert db.scalar(select(AnalysisRun)) is None
    assert client.get(docs_url, headers=owner).json()["status"] == "EMPTY"


# ---- 실패 ----


def test_llm_error_fails_run_without_partial_results(client, db, owner, docs_url, fake_llm, monkeypatch, caplog):
    monkeypatch.setattr(mms_settings, "mms_batch_chars", 60)
    _add_text(client, docs_url, owner, "가" * 50)
    _add_text(client, docs_url, owner, "나" * 50)
    fake_llm.responses = [
        {"requirements": [_req("첫 묶음 후보", quote=None)]},
        LLMTimeoutError("LLM_TIMEOUT", "AI 응답이 늦어지고 있습니다."),
    ]

    with caplog.at_level(logging.INFO, logger="app.features.maemusae"):
        assert _analyze(client, docs_url, owner).status_code == 202

    progress = client.get(f"{docs_url}/analysis", headers=owner).json()
    assert (progress["status"], progress["error_code"]) == ("FAILED", "LLM_TIMEOUT")
    assert progress["finished_at"] is not None
    assert client.get(docs_url, headers=owner).json()["status"] == "FAILED"
    assert _requirements(db, docs_url) == []  # 첫 묶음 결과도 남지 않음
    assert "code=LLM_TIMEOUT" in caplog.text


def test_failed_restart_keeps_previous_candidates(client, db, owner, docs_url, fake_llm):
    _add_text(client, docs_url, owner)
    fake_llm.responses = [{"requirements": [_req("회원가입")]}, LLMTimeoutError("LLM_TIMEOUT", "늦음")]
    assert _analyze(client, docs_url, owner).status_code == 202
    assert _analyze(client, docs_url, owner, restart=True).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["status"] == "FAILED"
    assert client.get(docs_url, headers=owner).json()["status"] == "READY"  # 기존 후보를 계속 씀
    assert [r.name for r in _requirements(db, docs_url)] == ["회원가입"]


# ---- 상태 확인 ----


def test_needs_sources(client, owner, docs_url, fake_llm):
    response = _analyze(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (400, "ANALYSIS_NO_SOURCES")


def test_restart_required_then_restart_deletes_all_and_numbers_from_one(client, db, owner, docs_url, fake_llm):
    """다시 분석하면 후보·직접 추가·입력을 모두 지우고 REQ-001 부터 (10/29 결정). 버전 기록은 그대로, saved_at 은 비움"""
    _add_text(client, docs_url, owner)
    fake_llm.responses = [{"requirements": [_req("회원가입"), _req("결제")]}]
    assert _analyze(client, docs_url, owner).status_code == 202
    manual = client.post(
        f"{docs_url}/requirements", json={"name": "직접 추가", "kind": "FUNCTIONAL", "priority": "LOW"}, headers=owner
    ).json()
    assert manual["code"] == "REQ-003"
    client.put(f"{docs_url}/requirements/{manual['id']}/notes/DESCRIPTION", json={"text": "메모"}, headers=owner)
    saved = client.post(f"{docs_url}/versions", headers=owner).json()
    assert saved["version_no"] == 1

    response = _analyze(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (409, "ANALYSIS_RESTART_REQUIRED")

    fake_llm.responses = [{"requirements": [_req("이메일 회원가입")]}]
    assert _analyze(client, docs_url, owner, restart=True).status_code == 202
    rows = db.scalars(select(Requirement).where(Requirement.document_id == _doc_id(docs_url))).all()
    assert [(r.seq, r.name, r.is_manual) for r in rows] == [(1, "이메일 회원가입", False)]
    assert db.scalars(select(RequirementNote)).all() == []
    document = client.get(docs_url, headers=owner).json()
    assert (document["saved_at"], document["last_version_no"], document["manual_count"]) == (None, 1, 0)
    # 남긴 버전은 그대로 (REQ-003 직접 추가와 입력 포함)
    version = client.get(f"{docs_url}/versions/{saved['id']}", headers=owner).json()
    assert [i["code"] for i in version["items"]] == ["REQ-001", "REQ-002", "REQ-003"]
    assert version["items"][2]["notes"][0]["text"] == "메모"


def test_manual_only_document_also_needs_restart(client, owner, docs_url, fake_llm):
    _add_text(client, docs_url, owner)
    client.post(f"{docs_url}/requirements", json={"name": "직접", "kind": "FUNCTIONAL", "priority": "LOW"}, headers=owner)
    response = _analyze(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (409, "ANALYSIS_RESTART_REQUIRED")


def test_busy_and_confirmed_documents(client, db, owner, docs_url, fake_llm, monkeypatch):
    _add_text(client, docs_url, owner)
    monkeypatch.setattr(runner, "run_analysis", lambda run_id: None)  # 분석이 계속 도는 상태로 둠

    assert _analyze(client, docs_url, owner).status_code == 202
    assert client.get(docs_url, headers=owner).json()["status"] == "ANALYZING"
    response = _analyze(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (409, "DOCUMENT_BUSY")
    # 분석 중에는 파일도 못 올림 (M2 규칙 그대로)
    assert client.post(f"{docs_url}/sources", data={"text": "추가"}, headers=owner).json()["code"] == "DOCUMENT_BUSY"

    db.execute(update(Document).where(Document.id == _doc_id(docs_url)).values(status="CONFIRMED"))
    db.commit()
    response = _analyze(client, docs_url, owner)
    assert (response.status_code, response.json()["code"]) == (409, "DOCUMENT_CONFIRMED")


def test_stale_running_analysis_is_cleaned_up(client, db, owner, docs_url, fake_llm, monkeypatch):
    _add_text(client, docs_url, owner)
    monkeypatch.setattr(runner, "run_analysis", lambda run_id: None)  # 서버가 재시작돼 멈춘 분석 흉내
    run_id = _analyze(client, docs_url, owner).json()["run_id"]

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["status"] == "RUNNING"  # 아직 15분 안 지남
    old = datetime.now(UTC) - timedelta(minutes=mms_settings.mms_analyze_stale_minutes + 1)
    db.execute(update(AnalysisRun).where(AnalysisRun.id == run_id).values(updated_at=old))
    db.commit()

    progress = client.get(f"{docs_url}/analysis", headers=owner).json()
    assert (progress["status"], progress["error_code"]) == ("FAILED", "ANALYSIS_INTERRUPTED")
    assert client.get(docs_url, headers=owner).json()["status"] == "FAILED"

    monkeypatch.undo()
    monkeypatch.setattr(runner, "open_session", lambda: nullcontext(db))
    fake_llm.responses = [{"requirements": [_req("회원가입")]}]
    assert _analyze(client, docs_url, owner).status_code == 202  # 다시 누르면 처음부터


def test_result_is_dropped_when_run_was_cleaned_up_meanwhile(client, db, owner, docs_url, fake_llm, monkeypatch):
    _add_text(client, docs_url, owner)
    extract = runner._extract_all

    def cleaned_up_during_ai_call(db_, run, plan, book):
        candidates = extract(db_, run, plan, book)
        # AI 를 부르는 동안 진행률 읽기가 멈춘 분석으로 보고 정리한 상황
        db_.execute(update(AnalysisRun).values(status="FAILED", error_code="ANALYSIS_INTERRUPTED"))
        db_.commit()
        return candidates

    monkeypatch.setattr(runner, "_extract_all", cleaned_up_during_ai_call)
    fake_llm.responses = [{"requirements": [_req("회원가입")]}]
    assert _analyze(client, docs_url, owner).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["error_code"] == "ANALYSIS_INTERRUPTED"
    assert _requirements(db, docs_url) == []  # 늦게 끝난 결과는 저장하지 않음


def test_no_analysis_yet_returns_null(client, owner, docs_url):
    response = client.get(f"{docs_url}/analysis", headers=owner)
    assert (response.status_code, response.json()) == (200, None)


# ---- 권한 ----


def test_member_can_analyze_master_and_outsider_cannot(client, db, headers, owner, docs_url, fake_llm):
    _add_text(client, docs_url, owner)
    project_id = int(docs_url.split("/")[4])
    member = headers("member01")
    user = db.scalar(select(User).where(User.login_id == "member01"))
    db.add(ProjectMember(project_id=project_id, user_id=user.id, role=MEMBER))
    db.commit()
    master = headers("master01", admin=True)
    outsider = headers("outsider01")

    # MASTER 는 멤버가 아니면 진행률만 보고, 분석은 403 (프로젝트를 이미 볼 수 있으니 404 로 숨기지 않음)
    response = _analyze(client, docs_url, master)
    assert (response.status_code, response.json()["code"]) == (403, "PROJECT_MEMBER_REQUIRED")
    assert _analyze(client, docs_url, outsider).status_code == 404
    assert client.get(f"{docs_url}/analysis", headers=outsider).status_code == 404

    fake_llm.responses = [{"requirements": [_req("회원가입")]}]
    assert _analyze(client, docs_url, member).status_code == 202
    assert client.get(f"{docs_url}/analysis", headers=master).json()["status"] == "SUCCEEDED"


def test_logs_have_no_document_text_or_prompt(client, owner, docs_url, fake_llm, caplog):
    _add_text(client, docs_url, owner)
    fake_llm.responses = [{"requirements": [_req("비밀 후보 이름")]}]
    with caplog.at_level(logging.INFO, logger="app"):
        assert _analyze(client, docs_url, owner, prompt="비밀 지시문").status_code == 202
    assert "AI 분석 끝" in caplog.text
    for secret in ("이메일로 가입한다", "비밀 후보 이름", "비밀 지시문"):
        assert secret not in caplog.text

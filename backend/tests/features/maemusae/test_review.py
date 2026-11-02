"""매무새 요구사항 후보 검토 API (M3-2): 목록·필터·커서, 상세(근거·입력), 수정(version), 일괄 수정, 직접 추가·삭제,
입력(사람마다 한 건), 입력 목록, 버전 추가·버전 저장(10/29), 문서 상태, 권한, 로그"""

import logging

import pytest
from sqlalchemy import select, text, update

from app.features.maemusae.analysis.models import Requirement, RequirementSource
from app.features.maemusae.documents.models import Document, SourcePage
from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.features.maemusae.review.models import RequirementNote
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


@pytest.fixture
def member(db, headers, docs_url):
    hdrs = headers("member01")
    user = db.scalar(select(User).where(User.login_id == "member01"))
    db.add(ProjectMember(project_id=int(docs_url.split("/")[4]), user_id=user.id, role=MEMBER))
    db.commit()
    return hdrs


@pytest.fixture
def seeded(client, db, owner, docs_url):
    """분석이 끝난 문서 흉내: 직접 쓴 글 1개 + AI 후보 3개 (REQ-001~003), 문서 READY"""
    assert client.post(f"{docs_url}/sources", data={"text": "회원은 이메일로 가입한다."}, headers=owner).status_code == 201
    page = db.scalar(select(SourcePage))
    doc_id = _doc_id(docs_url)
    rows = [
        Requirement(document_id=doc_id, seq=1, name="이메일 회원가입", kind="FUNCTIONAL", priority="HIGH",
                    description="이메일로 가입"),
        Requirement(document_id=doc_id, seq=2, name="카드 결제", kind="FUNCTIONAL", priority="MEDIUM",
                    ai_question="간편결제도 되나요?"),
        Requirement(document_id=doc_id, seq=3, name="응답 3초", kind="NON_FUNCTIONAL", priority="LOW",
                    priority_defaulted=True),
    ]
    db.add_all(rows)
    db.flush()
    db.add_all([
        RequirementSource(requirement_id=rows[0].id, source_page_id=page.id, quote="이메일로 가입한다", verified=True,
                          sort_order=1),
        RequirementSource(requirement_id=rows[1].id, source_page_id=page.id, quote="지어낸 문장", verified=False,
                          sort_order=1),
    ])
    db.execute(update(Document).where(Document.id == doc_id).values(status="READY"))
    db.commit()
    return {r.seq: r.id for r in rows}


def _list(client, url, hdrs, **params):
    response = client.get(f"{url}/requirements", params=params, headers=hdrs)
    assert response.status_code == 200, response.text
    return response.json()


def _codes(page) -> list[str]:
    return [item["code"] for item in page["items"]]


# ---- 목록 ----


def test_list_flags_and_filters(client, owner, docs_url, seeded):
    page = _list(client, docs_url, owner)
    assert _codes(page) == ["REQ-001", "REQ-002", "REQ-003"]
    first, second, third = page["items"]
    assert (first["verified_all"], first["needs_answer"]) == (True, False)
    assert (second["verified_all"], second["needs_answer"]) == (False, True)  # 위치 확인 필요 + 답 없는 질문
    assert (third["verified_all"], third["priority_defaulted"]) == (False, True)  # 근거 없음, 기본값 표시
    assert "description" not in first  # 목록은 가벼운 칸만

    assert _codes(_list(client, docs_url, owner, kind="NON_FUNCTIONAL")) == ["REQ-003"]
    assert _codes(_list(client, docs_url, owner, priority="HIGH")) == ["REQ-001"]
    assert _codes(_list(client, docs_url, owner, needs_check=True)) == ["REQ-002", "REQ-003"]
    assert _codes(_list(client, docs_url, owner, q="req-2")) == ["REQ-002"]  # 번호로
    assert _codes(_list(client, docs_url, owner, q="결제")) == ["REQ-002"]  # 이름으로
    assert _codes(_list(client, docs_url, owner, q="100%")) == []  # % 는 글자 그대로


def test_list_cursor_pages(client, owner, docs_url, seeded):
    page = _list(client, docs_url, owner, limit=2)
    assert _codes(page) == ["REQ-001", "REQ-002"]
    assert page["next_cursor"] == 2
    page = _list(client, docs_url, owner, limit=2, cursor=page["next_cursor"])
    assert (_codes(page), page["next_cursor"]) == (["REQ-003"], None)


# ---- 상세 ----


def test_detail_has_sources_and_notes(client, owner, member, docs_url, seeded):
    url = f"{docs_url}/requirements/{seeded[2]}"
    client.put(f"{url}/notes/ANSWER", json={"text": "간편결제도 필요"}, headers=member)

    detail = client.get(url, headers=owner).json()
    assert (detail["code"], detail["ai_question"], detail["needs_answer"]) == ("REQ-002", "간편결제도 되나요?", False)
    [source] = detail["sources"]
    assert (source["filename"], source["location_label"], source["verified"]) == ("직접 입력", "직접 입력", False)
    [note] = detail["notes"]
    assert (note["field"], note["text"], note["author_name"], note["mine"]) == ("ANSWER", "간편결제도 필요", "member01 이름", False)

    assert client.get(f"{docs_url}/requirements/999999", headers=owner).json()["code"] == "REQUIREMENT_NOT_FOUND"


# ---- 고치기 ----


def test_update_with_version_and_clears_defaulted(client, db, owner, docs_url, seeded):
    url = f"{docs_url}/requirements/{seeded[3]}"
    response = client.patch(url, json={"version": 1, "priority": "HIGH", "name": " 응답 2초 "}, headers=owner)
    assert response.status_code == 200, response.text
    item = response.json()
    assert (item["name"], item["priority"], item["priority_defaulted"], item["version"]) == ("응답 2초", "HIGH", False, 2)

    # 같은 version 으로 다시 보내면 다른 사람이 먼저 고친 것
    response = client.patch(url, json={"version": 1, "is_included": False}, headers=owner)
    assert (response.status_code, response.json()["code"]) == (409, "REQUIREMENT_CHANGED")
    assert "REQ-003" in response.json()["detail"]

    response = client.patch(url, json={"version": 2, "kind": "NOPE"}, headers=owner)
    assert (response.status_code, response.json()["code"]) == (400, "INVALID_CODE")
    response = client.patch(url, json={"version": 2, "name": "   "}, headers=owner)
    assert response.status_code == 422


def test_bulk_update_is_all_or_nothing(client, db, owner, docs_url, seeded):
    url = f"{docs_url}/requirements"
    response = client.patch(
        url,
        json={"items": [{"id": seeded[1], "version": 1, "is_included": False}, {"id": seeded[2], "version": 9, "is_included": False}]},
        headers=owner,
    )
    assert (response.status_code, response.json()["code"]) == (409, "REQUIREMENT_CHANGED")
    assert "REQ-002" in response.json()["detail"] and "REQ-001" not in response.json()["detail"]
    db.expire_all()
    assert db.get(Requirement, seeded[1]).is_included is True  # 하나도 안 바뀜

    items = [{"id": seeded[i], "version": 1, "is_included": False} for i in (1, 2)]
    response = client.patch(url, json={"items": items}, headers=owner)
    assert response.status_code == 200, response.text
    assert [(i["code"], i["is_included"], i["version"]) for i in response.json()] == [
        ("REQ-001", False, 2),
        ("REQ-002", False, 2),
    ]
    assert _codes(_list(client, docs_url, owner, included=False)) == ["REQ-001", "REQ-002"]

    duplicate = {"items": [{"id": seeded[1], "version": 2}, {"id": seeded[1], "version": 2}]}
    assert client.patch(url, json=duplicate, headers=owner).status_code == 422
    missing = {"items": [{"id": 999999, "version": 1}]}
    assert client.patch(url, json=missing, headers=owner).json()["code"] == "REQUIREMENT_NOT_FOUND"


# ---- 직접 추가·삭제 ----


def test_create_and_delete_manual_keeps_numbers(client, db, owner, docs_url, seeded):
    url = f"{docs_url}/requirements"
    body = {"name": "관리자 통계", "kind": "FUNCTIONAL", "priority": "LOW"}
    response = client.post(url, json=body, headers=owner)
    assert response.status_code == 201, response.text
    created = response.json()
    assert (created["code"], created["is_manual"]) == ("REQ-004", True)

    assert client.delete(f"{url}/{created['id']}", headers=owner).status_code == 204
    response = client.delete(f"{url}/{seeded[1]}", headers=owner)  # AI 후보는 못 지움
    assert (response.status_code, response.json()["code"]) == (409, "REQUIREMENT_NOT_DELETABLE")

    assert client.post(url, json={**body, "name": "다음 후보"}, headers=owner).json()["code"] == "REQ-005"  # 번호 다시 안 씀
    assert "REQ-004" not in _codes(_list(client, docs_url, owner))
    assert client.post(url, json={**body, "kind": "NOPE"}, headers=owner).json()["code"] == "INVALID_CODE"


def test_manual_add_on_empty_document_makes_it_ready(client, owner, docs_url):
    body = {"name": "첫 후보", "kind": "FUNCTIONAL", "priority": "MEDIUM"}
    assert client.post(f"{docs_url}/requirements", json=body, headers=owner).json()["code"] == "REQ-001"
    assert client.get(docs_url, headers=owner).json()["status"] == "READY"


# ---- 입력 ----


def test_notes_one_per_person_and_field(client, db, owner, member, docs_url, seeded):
    url = f"{docs_url}/requirements/{seeded[1]}/notes"
    assert client.put(f"{url}/DESCRIPTION", json={"text": "평균 3초"}, headers=owner).status_code == 200
    assert client.put(f"{url}/DESCRIPTION", json={"text": "최대 3초"}, headers=member).status_code == 200
    response = client.put(f"{url}/DESCRIPTION", json={"text": "평균 2초"}, headers=owner)  # 내 것만 고쳐짐
    assert response.json()["mine"] is True and response.json()["applied"] is False
    # 테스트는 한 트랜잭션이라 now() 가 같으므로 시각을 직접 정해 순서를 확인
    owner_note, _member_note = db.scalars(select(RequirementNote).order_by(RequirementNote.id)).all()
    db.execute(update(RequirementNote).where(RequirementNote.id == owner_note.id).values(updated_at=text("now() + interval '1 minute'")))
    db.commit()

    notes = client.get(f"{docs_url}/notes", headers=owner).json()
    assert [(n["text"], n["author_name"], n["mine"]) for n in notes] == [
        ("평균 2초", "owner01 이름", True),
        ("최대 3초", "member01 이름", False),
    ]
    oldest = client.get(f"{docs_url}/notes", params={"order": "oldest"}, headers=owner).json()
    assert [n["text"] for n in oldest] == ["최대 3초", "평균 2초"]
    member_id = db.scalar(select(User.id).where(User.login_id == "member01"))
    assert [n["text"] for n in client.get(f"{docs_url}/notes", params={"author_id": member_id}, headers=owner).json()] == ["최대 3초"]
    assert client.get(f"{docs_url}/notes", params={"q": "REQ-002"}, headers=owner).json() == []

    assert client.delete(f"{url}/DESCRIPTION", headers=member).status_code == 204
    assert client.delete(f"{url}/DESCRIPTION", headers=member).json()["code"] == "NOTE_NOT_FOUND"
    assert client.put(f"{url}/OTHER", json={"text": "x"}, headers=owner).status_code == 422
    assert client.put(f"{url}/ANSWER", json={"text": "  "}, headers=owner).status_code == 422


def test_editing_note_clears_applied_mark(client, db, owner, docs_url, seeded):
    url = f"{docs_url}/requirements/{seeded[2]}/notes/ANSWER"
    client.put(url, json={"text": "필요해요"}, headers=owner)
    # 다시 분류(M3-3)가 반영했다고 표시된 상태를 흉내
    from app.features.maemusae.analysis.models import AnalysisRun

    run = AnalysisRun(document_id=_doc_id(docs_url), run_type="REFINE", status="SUCCEEDED", requested_by=db.scalar(select(User.id)))
    db.add(run)
    db.flush()
    db.execute(update(RequirementNote).values(applied_run_id=run.id))
    db.commit()
    assert client.get(f"{docs_url}/notes", headers=owner).json()[0]["applied"] is True
    assert client.put(url, json={"text": "필요 없어요"}, headers=owner).json()["applied"] is False


def test_notes_of_deleted_requirements_are_hidden(client, db, owner, docs_url, seeded):
    client.put(f"{docs_url}/requirements/{seeded[1]}/notes/DESCRIPTION", json={"text": "메모"}, headers=owner)
    db.execute(update(Requirement).where(Requirement.id == seeded[1]).values(deleted_at=Requirement.created_at))
    db.commit()
    assert client.get(f"{docs_url}/notes", headers=owner).json() == []


# ---- 버전 추가·버전 저장 (10/29 결정, 계획 17의 2-1) ----


def _document(client, url, hdrs) -> dict:
    return client.get(url, headers=hdrs).json()


def _move_saved_at_back(db, url):
    # 테스트는 한 트랜잭션이라 now() 가 같음 → 저장 시각을 1분 앞으로 옮겨 '그 뒤에 고침'을 흉내
    db.execute(
        update(Document).where(Document.id == _doc_id(url)).values(saved_at=text("saved_at - interval '1 minute'"))
    )
    db.commit()


def test_add_version_always_makes_new_version_with_everything(client, owner, docs_url, seeded):
    client.put(f"{docs_url}/requirements/{seeded[2]}/notes/ANSWER", json={"text": "간편결제도요"}, headers=owner)
    first = client.post(f"{docs_url}/versions", headers=owner)
    second = client.post(f"{docs_url}/versions", headers=owner)
    assert (first.status_code, first.json()["version_no"], first.json()["overwritten"]) == (201, 1, False)
    assert (second.json()["version_no"], second.json()["overwritten"]) == (2, False)

    listed = client.get(f"{docs_url}/versions", headers=owner).json()
    assert [(v["kind"], v["version_no"], v["item_count"]) for v in listed] == [("SAVED", 2, 3), ("SAVED", 1, 3)]
    assert listed[0]["created_by_name"] == "owner01 이름"
    detail = client.get(f"{docs_url}/versions/{first.json()['id']}", headers=owner).json()
    assert [i["code"] for i in detail["items"]] == ["REQ-001", "REQ-002", "REQ-003"]
    assert detail["items"][0]["sources"][0]["quote"] == "이메일로 가입한다"
    assert detail["items"][1]["notes"][0] == {
        "field": "ANSWER", "text": "간편결제도요", "author_name": "owner01 이름",
        "updated_at": detail["items"][1]["notes"][0]["updated_at"],
    }
    assert detail["items"][2]["priority_defaulted"] is True

    document = _document(client, docs_url, owner)
    assert (document["last_version_no"], document["saved_at"] is not None, document["changed_since_save"]) == (2, True, False)


def test_save_version_overwrites_only_this_rounds_last_version(client, db, owner, docs_url, seeded):
    first = client.put(f"{docs_url}/versions/latest", headers=owner).json()
    assert (first["version_no"], first["overwritten"]) == (1, False)  # 버전이 없으면 새로

    client.patch(f"{docs_url}/requirements/{seeded[1]}", json={"version": 1, "name": "이메일 가입"}, headers=owner)
    again = client.put(f"{docs_url}/versions/latest", headers=owner).json()
    assert (again["id"], again["version_no"], again["overwritten"]) == (first["id"], 1, True)
    detail = client.get(f"{docs_url}/versions/{first['id']}", headers=owner).json()
    assert detail["items"][0]["name"] == "이메일 가입"
    assert detail["updated_by_name"] == "owner01 이름"

    # 다시 분석하면 runner 가 saved_at 을 비움 → 다음 버전 저장은 옛 분석의 v1 을 덮지 않고 v2 를 만듦
    db.execute(update(Document).where(Document.id == _doc_id(docs_url)).values(saved_at=None))
    db.commit()
    after = client.put(f"{docs_url}/versions/latest", headers=owner).json()
    assert (after["version_no"], after["overwritten"]) == (2, False)
    assert len(client.get(f"{docs_url}/versions", headers=owner).json()) == 2


def test_changed_since_save_catches_edits_notes_and_note_deletes(client, db, owner, docs_url, seeded):
    assert _document(client, docs_url, owner)["changed_since_save"] is False  # 버전이 없으면 false
    client.put(f"{docs_url}/requirements/{seeded[1]}/notes/DESCRIPTION", json={"text": "메모"}, headers=owner)
    client.post(f"{docs_url}/versions", headers=owner)
    _move_saved_at_back(db, docs_url)
    assert _document(client, docs_url, owner)["changed_since_save"] is True  # 저장 시각 뒤에 남긴 입력이 있음

    client.post(f"{docs_url}/versions", headers=owner)
    _move_saved_at_back(db, docs_url)
    db.execute(update(Requirement).values(updated_at=text("now() - interval '2 minutes'")))
    db.execute(update(RequirementNote).values(updated_at=text("now() - interval '2 minutes'")))
    db.commit()
    assert _document(client, docs_url, owner)["changed_since_save"] is False
    client.delete(f"{docs_url}/requirements/{seeded[1]}/notes/DESCRIPTION", headers=owner)
    assert _document(client, docs_url, owner)["changed_since_save"] is True  # 입력을 지운 것도 고친 것


def test_manual_count_and_empty_document_has_nothing_to_version(client, owner, docs_url):
    response = client.post(f"{docs_url}/versions", headers=owner)
    assert (response.status_code, response.json()["code"]) == (400, "NOTHING_TO_VERSION")
    client.post(f"{docs_url}/requirements", json={"name": "직접", "kind": "FUNCTIONAL", "priority": "LOW"}, headers=owner)
    document = _document(client, docs_url, owner)
    assert (document["manual_count"], document["last_version_no"], document["saved_at"]) == (1, None, None)


def test_version_of_other_document_is_404(client, owner, docs_url, seeded):
    version = client.post(f"{docs_url}/versions", headers=owner).json()
    other = client.post(PROJECTS, json=PROJECT, headers=owner).json()
    [other_doc] = client.get(f"{PROJECTS}/{other['id']}/documents", headers=owner).json()
    url = f"{PROJECTS}/{other['id']}/documents/{other_doc['id']}/versions/{version['id']}"
    assert (client.get(url, headers=owner).json()["code"]) == "VERSION_NOT_FOUND"


@pytest.mark.parametrize(("status", "code"), [("ANALYZING", "DOCUMENT_BUSY"), ("CONFIRMED", "DOCUMENT_CONFIRMED")])
def test_busy_or_confirmed_document_cannot_be_edited(client, db, owner, docs_url, seeded, status, code):
    db.execute(update(Document).where(Document.id == _doc_id(docs_url)).values(status=status))
    db.commit()
    url = f"{docs_url}/requirements"
    calls = [
        client.patch(f"{url}/{seeded[1]}", json={"version": 1, "is_included": False}, headers=owner),
        client.post(url, json={"name": "x", "kind": "FUNCTIONAL", "priority": "LOW"}, headers=owner),
        client.put(f"{url}/{seeded[1]}/notes/ANSWER", json={"text": "x"}, headers=owner),
        client.post(f"{docs_url}/versions", headers=owner),
        client.put(f"{docs_url}/versions/latest", headers=owner),
    ]
    assert [(c.status_code, c.json()["code"]) for c in calls] == [(409, code)] * 5
    assert _codes(_list(client, docs_url, owner)) == ["REQ-001", "REQ-002", "REQ-003"]  # 읽기는 됨


# ---- 권한 ----


def test_master_reads_only_and_outsider_gets_404(client, headers, owner, docs_url, seeded):
    master = headers("master01", admin=True)
    outsider = headers("outsider01")
    assert _codes(_list(client, docs_url, master)) == ["REQ-001", "REQ-002", "REQ-003"]
    assert client.get(f"{docs_url}/requirements/{seeded[1]}", headers=master).status_code == 200
    assert client.get(f"{docs_url}/notes", headers=master).status_code == 200

    response = client.patch(f"{docs_url}/requirements/{seeded[1]}", json={"version": 1, "is_included": False}, headers=master)
    assert (response.status_code, response.json()["code"]) == (403, "PROJECT_MEMBER_REQUIRED")
    assert client.post(f"{docs_url}/versions", headers=master).status_code == 403
    assert client.put(f"{docs_url}/versions/latest", headers=master).status_code == 403
    assert client.get(f"{docs_url}/versions", headers=master).status_code == 200

    assert client.get(f"{docs_url}/requirements", headers=outsider).status_code == 404
    assert client.get(f"{docs_url}/versions", headers=outsider).status_code == 404
    assert client.patch(f"{docs_url}/requirements/{seeded[1]}", json={"version": 1}, headers=outsider).status_code == 404


def test_member_can_edit(client, member, docs_url, seeded):
    response = client.patch(f"{docs_url}/requirements/{seeded[1]}", json={"version": 1, "is_included": False}, headers=member)
    assert response.status_code == 200


def test_logs_have_no_content(client, owner, docs_url, seeded, caplog):
    with caplog.at_level(logging.INFO, logger="app.features.maemusae"):
        client.patch(f"{docs_url}/requirements/{seeded[1]}", json={"version": 1, "name": "비밀 이름"}, headers=owner)
        client.put(f"{docs_url}/requirements/{seeded[1]}/notes/ANSWER", json={"text": "비밀 답"}, headers=owner)
    assert "fields=name" in caplog.text
    assert "비밀 이름" not in caplog.text and "비밀 답" not in caplog.text

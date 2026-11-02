"""매무새 프로젝트·멤버 API와 프로젝트 접근 검사 (access.py)"""

import logging

import pytest
from sqlalchemy import select

from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.users import roles
from app.users import service as user_service
from app.users.models import User

BASE = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}


@pytest.fixture
def headers(db, make_user, login):
    """headers("owner01") → 그 아이디로 가입(없으면)·로그인한 헤더"""

    def _headers(login_id: str, *, admin: bool = False) -> dict[str, str]:
        if db.scalar(select(User).where(User.login_id == login_id)) is None:
            make_user(login_id, admin=admin, name=f"{login_id} 이름")
        return login(login_id)

    return _headers


@pytest.fixture
def project(client, headers):
    """owner01 이 만든 프로젝트"""
    response = client.post(BASE, json=PROJECT, headers=headers("owner01"))
    assert response.status_code == 201, response.text
    return response.json()


def _add_member(db, make_user, project_id: int, login_id: str, role: str = MEMBER) -> ProjectMember:
    """초대(M2)가 아직 없어서 테스트에서는 멤버 행을 직접 넣습니다"""
    user = make_user(login_id, name=f"{login_id} 이름")
    member = ProjectMember(project_id=project_id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    return member


def _members(client, project_id, hdrs) -> dict[str, dict]:
    response = client.get(f"{BASE}/{project_id}/members", headers=hdrs)
    assert response.status_code == 200, response.text
    return {m["user_id"]: m for m in response.json()}


# ---- 로그인·만들기·목록 ----


def test_all_project_apis_need_login(client):
    for method, path in [("get", BASE), ("post", BASE), ("get", f"{BASE}/1"), ("get", f"{BASE}/1/members")]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["code"] == "UNAUTHORIZED"


def test_create_project_makes_creator_admin(client, headers, project):
    assert project["name"] == "쇼핑몰 리뉴얼"
    assert project["my_role"] == "ADMIN"
    assert project["member_count"] == 1

    members = _members(client, project["id"], headers("owner01"))
    assert members["owner01"]["role"] == "ADMIN"
    assert members["owner01"]["name"] == "owner01 이름"
    assert "email" not in members["owner01"]  # 이메일은 멤버끼리도 보여 주지 않음


def test_create_project_validates_name_and_period(client, headers):
    hdrs = headers("owner01")
    response = client.post(BASE, json={**PROJECT, "name": "   "}, headers=hdrs)
    assert response.status_code == 422
    response = client.post(BASE, json={**PROJECT, "end_date": "2026-10-01"}, headers=hdrs)
    assert response.status_code == 422
    response = client.post(BASE, json={**PROJECT, "name": "  공백 정리  "}, headers=hdrs)
    assert response.json()["name"] == "공백 정리"


def test_list_shows_only_my_projects_with_search_and_paging(client, headers, db, make_user):
    owner = headers("owner01")
    for name in ["쇼핑몰 리뉴얼", "사내 메신저", "쇼핑몰 앱"]:
        assert client.post(BASE, json={**PROJECT, "name": name}, headers=owner).status_code == 201
    other = client.post(BASE, json={**PROJECT, "name": "남의 쇼핑몰"}, headers=headers("other01")).json()

    body = client.get(BASE, headers=owner).json()
    assert body["total"] == 3
    assert [p["name"] for p in body["items"]] == ["쇼핑몰 앱", "사내 메신저", "쇼핑몰 리뉴얼"]  # 최근 만든 순

    body = client.get(BASE, params={"q": "쇼핑몰", "size": 1}, headers=owner).json()
    assert body["total"] == 2 and len(body["items"]) == 1
    assert body["items"][0]["name"] == "쇼핑몰 앱"

    # % 와 _ 는 글자 그대로 찾음
    assert client.get(BASE, params={"q": "%"}, headers=owner).json()["total"] == 0

    # 남의 프로젝트에 멤버로 들어가면 내 목록에 보이고, 역할·멤버 수가 맞음
    _add_member(db, make_user, other["id"], "member01")
    body = client.get(BASE, headers=headers("member01")).json()
    assert [(p["name"], p["my_role"], p["member_count"]) for p in body["items"]] == [("남의 쇼핑몰", "MEMBER", 2)]


# ---- 접근 검사 ----


def test_non_member_gets_404_not_403(client, headers, project):
    hdrs = headers("stranger01")
    for method, path in [
        ("get", f"{BASE}/{project['id']}"),
        ("get", f"{BASE}/{project['id']}/members"),
        ("patch", f"{BASE}/{project['id']}"),
        ("delete", f"{BASE}/{project['id']}"),
    ]:
        response = getattr(client, method)(path, headers=hdrs, **({"json": {"name": "x"}} if method == "patch" else {}))
        assert response.status_code == 404, path
        assert response.json()["code"] == "PROJECT_NOT_FOUND"
    assert client.get(f"{BASE}/999999", headers=hdrs).json()["code"] == "PROJECT_NOT_FOUND"


def test_member_can_view_but_not_manage(client, headers, project, db, make_user):
    _add_member(db, make_user, project["id"], "member01")
    hdrs = headers("member01")

    detail = client.get(f"{BASE}/{project['id']}", headers=hdrs).json()
    assert detail["my_role"] == "MEMBER" and detail["member_count"] == 2

    response = client.patch(f"{BASE}/{project['id']}", json={"name": "바꿈"}, headers=hdrs)
    assert response.status_code == 403
    assert response.json()["code"] == "PROJECT_ADMIN_REQUIRED"
    assert client.delete(f"{BASE}/{project['id']}", headers=hdrs).status_code == 403


@pytest.fixture
def app_logs_visible():
    # app 로거는 propagate=False 라서 caplog 가 받도록 테스트 동안만 켭니다 (하네스 pytest-app-logging)
    logger = logging.getLogger("app")
    logger.propagate = True
    yield
    logger.propagate = False


def test_master_can_only_view_and_view_is_logged(client, headers, project, caplog, app_logs_visible):
    hdrs = headers("master01", admin=True)
    with caplog.at_level(logging.INFO, logger="app.features.maemusae.access"):
        detail = client.get(f"{BASE}/{project['id']}", headers=hdrs)
    assert detail.status_code == 200
    assert detail.json()["my_role"] is None
    assert f"MASTER 프로젝트 열람 project_id={project['id']}" in caplog.text
    assert "쇼핑몰" not in caplog.text  # 내용은 남기지 않음

    assert client.get(f"{BASE}/{project['id']}/members", headers=hdrs).status_code == 200
    # 쓰기는 멤버만: MASTER 라도 404
    assert client.patch(f"{BASE}/{project['id']}", json={"name": "바꿈"}, headers=hdrs).status_code == 404
    assert client.delete(f"{BASE}/{project['id']}", headers=hdrs).status_code == 404
    # 내 목록에는 남의 프로젝트가 나오지 않음
    assert client.get(BASE, headers=hdrs).json()["total"] == 0


def test_removed_member_is_blocked_with_the_same_token(client, headers, project, db, make_user):
    """프로젝트 역할도 요청마다 DB 에서 읽으므로, 내보내면 이미 받은 토큰으로도 바로 막힙니다."""
    member = _add_member(db, make_user, project["id"], "member01")
    hdrs = headers("member01")
    assert client.get(f"{BASE}/{project['id']}", headers=hdrs).status_code == 200

    owner = headers("owner01")
    assert client.delete(f"{BASE}/{project['id']}/members/{member.id}", headers=owner).status_code == 204
    assert client.get(f"{BASE}/{project['id']}", headers=hdrs).status_code == 404


# ---- 수정·삭제 ----


def test_admin_updates_project(client, headers, project):
    owner = headers("owner01")
    response = client.patch(f"{BASE}/{project['id']}", json={"name": "쇼핑몰 2차", "end_date": "2027-01-31"}, headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "쇼핑몰 2차"
    assert response.json()["end_date"] == "2027-01-31"
    assert response.json()["start_date"] == "2026-11-01"


def test_update_rejects_bad_period_and_empty_body(client, headers, project):
    owner = headers("owner01")
    response = client.patch(f"{BASE}/{project['id']}", json={"end_date": "2026-10-01"}, headers=owner)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PERIOD"
    assert client.patch(f"{BASE}/{project['id']}", json={}, headers=owner).status_code == 422
    assert client.patch(f"{BASE}/{project['id']}", json={"name": None}, headers=owner).status_code == 422
    assert client.patch(f"{BASE}/{project['id']}", json={"created_by": 1}, headers=owner).status_code == 422


def test_deleted_project_disappears(client, headers, project, db):
    owner = headers("owner01")
    assert client.delete(f"{BASE}/{project['id']}", headers=owner).status_code == 204
    assert client.get(f"{BASE}/{project['id']}", headers=owner).status_code == 404
    assert client.get(BASE, headers=owner).json()["total"] == 0
    master = headers("master01", admin=True)
    assert client.get(f"{BASE}/{project['id']}", headers=master).status_code == 404


# ---- 멤버 ----


def test_admin_changes_roles_and_last_admin_is_kept(client, headers, project, db, make_user):
    owner = headers("owner01")
    member = _add_member(db, make_user, project["id"], "member01")
    owner_member_id = _members(client, project["id"], owner)["owner01"]["id"]

    # 혼자 남은 관리자는 강등할 수 없음
    response = client.patch(f"{BASE}/{project['id']}/members/{owner_member_id}", json={"role": "MEMBER"}, headers=owner)
    assert response.status_code == 409
    assert response.json()["code"] == "LAST_PROJECT_ADMIN"

    # 다른 멤버를 관리자로 올리면 강등 가능
    response = client.patch(f"{BASE}/{project['id']}/members/{member.id}", json={"role": "ADMIN"}, headers=owner)
    assert response.status_code == 200
    assert response.json() == {**response.json(), "user_id": "member01", "role": "ADMIN"}
    response = client.patch(f"{BASE}/{project['id']}/members/{owner_member_id}", json={"role": "MEMBER"}, headers=owner)
    assert response.status_code == 200

    # owner01 은 이제 일반 멤버라 관리 불가
    response = client.patch(f"{BASE}/{project['id']}/members/{member.id}", json={"role": "MEMBER"}, headers=owner)
    assert response.status_code == 403
    assert client.get(f"{BASE}/{project['id']}", headers=owner).json()["my_role"] == "MEMBER"


def test_member_role_validation(client, headers, project):
    owner = headers("owner01")
    owner_member_id = _members(client, project["id"], owner)["owner01"]["id"]
    url = f"{BASE}/{project['id']}/members/{owner_member_id}"
    assert client.patch(url, json={"role": "MASTER"}, headers=owner).status_code == 422
    response = client.patch(f"{BASE}/{project['id']}/members/999999", json={"role": "MEMBER"}, headers=owner)
    assert response.status_code == 404
    assert response.json()["code"] == "PROJECT_MEMBER_NOT_FOUND"


def test_member_can_leave_but_not_remove_others(client, headers, project, db, make_user):
    m1 = _add_member(db, make_user, project["id"], "member01")
    m2 = _add_member(db, make_user, project["id"], "member02")
    hdrs = headers("member01")

    response = client.delete(f"{BASE}/{project['id']}/members/{m2.id}", headers=hdrs)
    assert response.status_code == 403
    assert response.json()["code"] == "PROJECT_ADMIN_REQUIRED"

    assert client.delete(f"{BASE}/{project['id']}/members/{m1.id}", headers=hdrs).status_code == 204
    assert set(_members(client, project["id"], headers("owner01"))) == {"owner01", "member02"}


def test_last_admin_cannot_leave(client, headers, project):
    owner = headers("owner01")
    owner_member_id = _members(client, project["id"], owner)["owner01"]["id"]
    response = client.delete(f"{BASE}/{project['id']}/members/{owner_member_id}", headers=owner)
    assert response.status_code == 409
    assert response.json()["code"] == "LAST_PROJECT_ADMIN"


def test_member_of_another_project_cannot_be_touched(client, headers, project, db, make_user):
    """다른 프로젝트의 멤버 번호를 넣어도 이 프로젝트에서는 찾지 못합니다."""
    other = client.post(BASE, json=PROJECT, headers=headers("other01")).json()
    outsider = _add_member(db, make_user, other["id"], "member01")
    owner = headers("owner01")
    response = client.delete(f"{BASE}/{project['id']}/members/{outsider.id}", headers=owner)
    assert response.status_code == 404
    assert response.json()["code"] == "PROJECT_MEMBER_NOT_FOUND"


def test_kit_roles_do_not_grant_project_roles(client, project, db, login):
    """킷 역할(OWNER, WRITER 등)은 프로젝트 권한과 상관없습니다. 멤버가 아니면 404 (결정 1)."""
    user_service.create_user(
        db, login_id="writer01", email="writer01@example.com", password="password123",  # conftest 의 PASSWORD
        name="작가", profile={}, roles=[roles.OWNER, roles.WRITER],
    )
    response = client.get(f"{BASE}/{project['id']}", headers=login("writer01"))
    assert response.status_code == 404

"""매무새 초대: 보내기·대기 목록·취소(관리자), 링크 열기·가입 증표·수락(링크를 가진 사람)"""

import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.features.maemusae.invitations.mail import build_invite
from app.features.maemusae.invitations.models import ProjectInvitation
from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.users.models import User

PROJECTS = "/api/mms/projects"
LINKS = "/api/mms/invitations"
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
def project(client, headers):
    response = client.post(PROJECTS, json=PROJECT, headers=headers("owner01"))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def invite(client, headers, project, mail_outbox):
    """invite("dana@example.com") → 관리자 owner01 이 초대하고 메일 링크의 토큰을 돌려줌"""

    def _invite(email: str, role: str = "MEMBER") -> str:
        response = client.post(
            f"{PROJECTS}/{project['id']}/invitations", json={"email": email, "role": role}, headers=headers("owner01")
        )
        assert response.status_code == 201, response.text
        return _token_from(mail_outbox[-1])

    return _invite


def _token_from(message) -> str:
    return re.search(r"/maemusae/invite\?token=(\S+)", message.text).group(1)


def _members(client, project_id, hdrs) -> dict[str, dict]:
    response = client.get(f"{PROJECTS}/{project_id}/members", headers=hdrs)
    assert response.status_code == 200, response.text
    return {m["user_id"]: m for m in response.json()}


def _accept(client, token, hdrs):
    return client.post(f"{LINKS}/accept", json={"token": token}, headers=hdrs)


# ---- 관리자: 보내기·목록·취소 ----


def test_invite_sends_mail_and_shows_pending(client, headers, project, invite, mail_outbox):
    token = invite("Dana@Example.com", "ADMIN")

    message = mail_outbox[-1]
    assert message.to == "dana@example.com"  # 소문자로 저장·발송
    assert message.template == "mms_invite"
    assert "쇼핑몰 리뉴얼" in message.subject and "owner01 이름" in message.subject
    assert "7일" in message.text and "관리자" in message.text
    assert len(token) >= 40

    response = client.get(f"{PROJECTS}/{project['id']}/invitations", headers=headers("owner01"))
    assert response.status_code == 200
    [pending] = response.json()
    assert pending["email"] == "dana@example.com"
    assert pending["role"] == "ADMIN"
    assert pending["invited_by_name"] == "owner01 이름"
    assert "token" not in pending and "token_hash" not in pending


def test_token_is_stored_only_as_hash(db, invite):
    token = invite("dana@example.com")
    row = db.scalar(select(ProjectInvitation))
    assert row.token_hash != token and token not in row.token_hash
    assert len(row.token_hash) == 64


def test_only_project_admin_manages_invitations(client, db, headers, make_user, project):
    member = make_user("member01")
    db.add(ProjectMember(project_id=project["id"], user_id=member.id, role=MEMBER))
    db.commit()
    url = f"{PROJECTS}/{project['id']}/invitations"
    body = {"email": "dana@example.com"}

    assert client.post(url, json=body).status_code == 401
    response = client.post(url, json=body, headers=headers("member01"))
    assert response.status_code == 403
    assert response.json()["code"] == "PROJECT_ADMIN_REQUIRED"
    assert client.get(url, headers=headers("member01")).status_code == 403
    # 멤버가 아니면 서비스 MASTER 라도 프로젝트가 있는지 모르게 404
    assert client.post(url, json=body, headers=headers("stranger01")).status_code == 404
    assert client.get(url, headers=headers("master01", admin=True)).status_code == 404


def test_invite_rejects_existing_member_and_bad_input(client, headers, project, make_user):
    url = f"{PROJECTS}/{project['id']}/invitations"
    response = client.post(url, json={"email": "owner01@example.com"}, headers=headers("owner01"))
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_MEMBER"
    assert client.post(url, json={"email": "not-an-email"}, headers=headers("owner01")).status_code == 422
    assert client.post(url, json={"email": "a@example.com", "role": "MASTER"}, headers=headers("owner01")).status_code == 422


def test_reinvite_invalidates_previous_link(client, headers, project, invite):
    old = invite("dana@example.com")
    new = invite("dana@example.com", "ADMIN")

    response = client.post(f"{LINKS}/lookup", json={"token": old})
    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_INVALID"
    assert client.post(f"{LINKS}/lookup", json={"token": new}).json()["role"] == "ADMIN"
    pending = client.get(f"{PROJECTS}/{project['id']}/invitations", headers=headers("owner01")).json()
    assert len(pending) == 1


def test_revoke_invitation(client, headers, project, invite):
    token = invite("dana@example.com")
    [pending] = client.get(f"{PROJECTS}/{project['id']}/invitations", headers=headers("owner01")).json()

    url = f"{PROJECTS}/{project['id']}/invitations/{pending['id']}"
    assert client.delete(url, headers=headers("owner01")).status_code == 204
    assert client.delete(url, headers=headers("owner01")).json()["code"] == "INVITATION_NOT_FOUND"
    assert client.post(f"{LINKS}/lookup", json={"token": token}).status_code == 404
    assert client.get(f"{PROJECTS}/{project['id']}/invitations", headers=headers("owner01")).json() == []


# ---- 링크: 가입 전인 사람 ----


def test_new_user_flow_lookup_proof_signup_accept(client, db, headers, project, invite, login):
    token = invite("dana@example.com")

    info = client.post(f"{LINKS}/lookup", json={"token": token}).json()
    assert info == {
        "project_name": "쇼핑몰 리뉴얼",
        "invited_by_name": "owner01 이름",
        "role": "MEMBER",
        "email": "dana@example.com",
        "expires_at": info["expires_at"],
        "account_exists": False,
    }

    proof = client.post(f"{LINKS}/signup-proof", json={"token": token})
    assert proof.status_code == 200, proof.text
    assert proof.json()["email"] == "dana@example.com"

    # 인증번호 없이 증표로 킷 가입
    signup = client.post(
        "/api/auth/signup",
        json={
            "user_id": "dana01",
            "email": "dana@example.com",
            "password": "password123",
            "name": "김다나",
            "agreed_terms": ["terms", "privacy"],
            "email_verification_token": proof.json()["email_verification_token"],
        },
    )
    assert signup.status_code == 201, signup.text

    response = _accept(client, token, login("dana01"))
    assert response.status_code == 200, response.text
    assert response.json() == {"project_id": project["id"], "role": "MEMBER"}

    members = _members(client, project["id"], headers("owner01"))
    assert members["dana01"]["role"] == "MEMBER"
    row = db.scalar(select(ProjectInvitation))
    assert row.accepted_at is not None and row.accepted_user_id is not None
    member = db.scalar(select(ProjectMember).where(ProjectMember.user_id == row.accepted_user_id))
    assert member.invitation_id == row.id

    # 토큰은 한 번만, 수락한 초대는 대기 목록에서 빠짐
    again = _accept(client, token, login("dana01"))
    assert again.status_code == 404
    assert again.json()["code"] == "INVITATION_INVALID"
    assert client.get(f"{PROJECTS}/{project['id']}/invitations", headers=headers("owner01")).json() == []


def test_signup_proof_only_works_for_the_invited_email(client, invite, signup):
    token = invite("dana@example.com")
    proof = client.post(f"{LINKS}/signup-proof", json={"token": token}).json()["email_verification_token"]

    # 증표는 초대 이메일에만 맞습니다. 다른 이메일로 가입하려 하면 킷이 막음
    response = signup("other01", email="other@example.com", email_verification_token=proof)
    assert response.status_code == 400
    assert response.json()["code"] == "EMAIL_VERIFICATION_REQUIRED"


# ---- 링크: 이미 가입한 사람 ----


def test_existing_user_logs_in_and_accepts(client, headers, project, invite, make_user, login):
    make_user("dana01", email="dana@example.com", name="김다나")
    token = invite("dana@example.com", "ADMIN")

    assert client.post(f"{LINKS}/lookup", json={"token": token}).json()["account_exists"] is True
    proof = client.post(f"{LINKS}/signup-proof", json={"token": token})
    assert proof.status_code == 409
    assert proof.json()["code"] == "EMAIL_TAKEN"

    assert client.post(f"{LINKS}/accept", json={"token": token}).status_code == 401  # 로그인 필요
    response = _accept(client, token, login("dana01"))
    assert response.json() == {"project_id": project["id"], "role": "ADMIN"}
    assert _members(client, project["id"], headers("owner01"))["dana01"]["role"] == "ADMIN"


def test_accept_requires_same_email(client, invite, make_user, login):
    make_user("other01", email="other@example.com")
    make_user("dana01", email="dana@example.com")
    token = invite("dana@example.com")

    response = _accept(client, token, login("other01"))
    assert response.status_code == 403
    assert response.json()["code"] == "INVITATION_EMAIL_MISMATCH"
    # 다른 사람이 시도해도 초대는 그대로 살아 있음
    assert _accept(client, token, login("dana01")).status_code == 200


# ---- 쓸 수 없는 토큰 ----


def test_expired_unknown_and_deleted_project_tokens_look_the_same(client, db, headers, project, invite):
    expired = invite("dana@example.com")
    db.execute(update(ProjectInvitation).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    live = invite("kim@example.com")

    for token in (expired, "unknown-token"):
        for path in ("lookup", "signup-proof"):
            response = client.post(f"{LINKS}/{path}", json={"token": token})
            assert response.status_code == 404, (token, path)
            assert response.json()["code"] == "INVITATION_INVALID"

    # 프로젝트가 삭제 표시되면 그 초대도 못 씀
    assert client.delete(f"{PROJECTS}/{project['id']}", headers=headers("owner01")).status_code == 204
    assert client.post(f"{LINKS}/lookup", json={"token": live}).json()["code"] == "INVITATION_INVALID"


def test_logs_have_no_token_or_email(client, invite, make_user, login, caplog):
    make_user("dana01", email="dana@example.com")
    with caplog.at_level(logging.INFO, logger="app.features.maemusae"):
        token = invite("dana@example.com")
        client.post(f"{LINKS}/lookup", json={"token": token})
        _accept(client, token, login("dana01"))

    # 매무새 로그만 봅니다 (킷 메일 로그는 받는 사람 주소를 남기는 킷 동작이라 여기서 다루지 않음)
    text = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app.features.maemusae"))
    assert "프로젝트 초대 project_id=" in text
    assert "프로젝트 초대 수락" in text
    assert token not in caplog.text  # 토큰은 어떤 로그에도 없음 (주소가 아니라 본문으로 받음)
    assert "dana@example.com" not in text


def test_invite_mail_escapes_html():
    rendered = build_invite(
        {"project_name": "<b>X</b>", "inviter_name": "A&B", "role": "MEMBER", "link": "https://x/?a=1&b=2", "expire_days": 7}
    )
    assert "<b>X</b>" not in rendered.html
    assert "&lt;b&gt;X&lt;/b&gt;" in rendered.html
    assert "A&amp;B" in rendered.html

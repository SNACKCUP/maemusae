"""매무새 초대 이메일 암호화 (계획 23 M2): DB 에는 암호문·지문만, 찾기는 지문으로"""

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text

from app.crypto import decrypt, email_index
from app.features.maemusae.invitations.models import ProjectInvitation
from app.users.models import User

PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}


def _owner_project(client, db, make_user, login) -> tuple[dict, dict]:
    if db.scalar(select(User).where(User.login_id == "owner01")) is None:
        make_user("owner01", name="owner01 이름")
    hdrs = login("owner01")
    response = client.post(PROJECTS, json=PROJECT, headers=hdrs)
    assert response.status_code == 201, response.text
    return response.json(), hdrs


def _invite(client, project, hdrs, email: str) -> None:
    response = client.post(
        f"{PROJECTS}/{project['id']}/invitations", json={"email": email, "role": "MEMBER"}, headers=hdrs
    )
    assert response.status_code == 201, response.text


def _pending(client, project, hdrs) -> list[dict]:
    response = client.get(f"{PROJECTS}/{project['id']}/invitations", headers=hdrs)
    assert response.status_code == 200, response.text
    return response.json()


def test_invite_stores_only_ciphertext_and_hash(client, db, make_user, login, mail_outbox):
    project, hdrs = _owner_project(client, db, make_user, login)
    _invite(client, project, hdrs, "Dana@Example.com")

    inv = db.scalar(select(ProjectInvitation).where(ProjectInvitation.project_id == project["id"]))
    assert inv.email == "dana@example.com"  # 속성으로 읽으면 풀린 값
    assert inv.email_hash == email_index("DANA@example.com")  # 대소문자 무시

    raw = db.execute(
        text("SELECT email_enc FROM mms_project_invitations WHERE id = :id"), {"id": inv.id}
    ).scalar_one()
    assert b"dana" not in bytes(raw)  # DB 에는 암호문만
    assert decrypt(bytes(raw), "mms_project_invitations.email") == "dana@example.com"


def test_plaintext_email_column_is_gone(db):
    columns = {c["name"] for c in sa_inspect(db.get_bind()).get_columns("mms_project_invitations")}
    assert "email" not in columns
    assert {"email_enc", "email_hash"} <= columns


def test_reinvite_with_other_case_replaces_live_invite(client, db, make_user, login, mail_outbox):
    """살아 있는 초대 하나만 (project_id, email_hash): 대소문자만 다른 이메일로 다시 초대하면 이전 초대가 무효"""
    project, hdrs = _owner_project(client, db, make_user, login)
    _invite(client, project, hdrs, "dana@example.com")
    _invite(client, project, hdrs, "DANA@EXAMPLE.COM")

    pending = _pending(client, project, hdrs)
    assert [p["email"] for p in pending] == ["dana@example.com"]

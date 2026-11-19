"""매무새 초대 이메일 암호화 (계획 23 M1): 저장할 때 암호문·지문을 같이 채우고, 채우기 명령이 기존 행을 채움"""

from sqlalchemy import select, text

from app.crypto import decrypt, email_index
from app.features.maemusae.invitations import pii_backfill
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


def test_invite_stores_email_ciphertext_and_hash(client, db, make_user, login, mail_outbox):
    project, hdrs = _owner_project(client, db, make_user, login)
    _invite(client, project, hdrs, "Dana@Example.com")

    inv = db.scalar(select(ProjectInvitation).where(ProjectInvitation.project_id == project["id"]))
    db.refresh(inv)
    assert inv.email == "dana@example.com"
    assert inv.email_enc == "dana@example.com"  # 속성으로 읽으면 풀린 값
    assert inv.email_hash == email_index("DANA@example.com")  # 대소문자 무시

    raw = db.execute(
        text("SELECT email_enc FROM mms_project_invitations WHERE id = :id"), {"id": inv.id}
    ).scalar_one()
    assert b"dana" not in bytes(raw)  # DB 에는 암호문만
    assert decrypt(bytes(raw), "mms_project_invitations.email") == "dana@example.com"


def test_backfill_fills_old_rows(client, db, make_user, login, mail_outbox):
    project, hdrs = _owner_project(client, db, make_user, login)
    _invite(client, project, hdrs, "old@example.com")
    _invite(client, project, hdrs, "older@example.com")
    # M1 이전에 만든 행처럼 암호화 칸을 비움
    db.execute(text("UPDATE mms_project_invitations SET email_enc = NULL, email_hash = NULL"))
    db.commit()

    assert pii_backfill.backfill(db, dry_run=True) == 2
    assert pii_backfill.backfill(db, batch_size=1) == 2
    assert pii_backfill.backfill(db, dry_run=True) == 0

    db.expire_all()
    rows = db.scalars(select(ProjectInvitation).order_by(ProjectInvitation.id)).all()
    assert [r.email_enc for r in rows] == ["old@example.com", "older@example.com"]
    assert [r.email_hash for r in rows] == [email_index("old@example.com"), email_index("older@example.com")]


def test_backfill_command_dry_run_succeeds(db):
    assert pii_backfill.main(["--dry-run"]) == 0


def test_backfill_command_loads_related_tables_on_its_own():
    """명령으로 따로 실행하면 앱 전체 모델이 안 올라옴. 초대가 가리키는 테이블도 직접 불러와야 저장할 수 있음
    (2026-11-19 운영 pii-backfill 이 NoReferencedTableError: mms_projects 로 실패했던 문제)"""
    import subprocess
    import sys

    code = (
        "import app.features.maemusae.invitations.pii_backfill\n"
        "from app.features.maemusae.invitations.models import ProjectInvitation\n"
        "ProjectInvitation.__mapper__.base_mapper._sorted_tables\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr[-2000:]

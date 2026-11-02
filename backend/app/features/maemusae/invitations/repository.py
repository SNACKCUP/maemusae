"""초대 테이블 접근. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.features.maemusae.invitations.models import ProjectInvitation
from app.users.models import User


def _live(now: datetime):
    return (
        ProjectInvitation.accepted_at.is_(None),
        ProjectInvitation.revoked_at.is_(None),
        ProjectInvitation.expires_at > now,
    )


def revoke_live(db: Session, project_id: int, email: str, now: datetime) -> None:
    """같은 프로젝트·이메일의 살아 있는 초대를 모두 무효로 (만료된 것도 포함해 정리)"""
    db.execute(
        update(ProjectInvitation)
        .where(
            ProjectInvitation.project_id == project_id,
            ProjectInvitation.email == email,
            ProjectInvitation.accepted_at.is_(None),
            ProjectInvitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def list_live(db: Session, project_id: int, now: datetime) -> list[tuple[ProjectInvitation, str]]:
    """대기 중인 초대와 초대한 사람 이름. 최근 보낸 순"""
    rows = db.execute(
        select(ProjectInvitation, User.name)
        .join(User, User.id == ProjectInvitation.invited_by)
        .where(ProjectInvitation.project_id == project_id, *_live(now))
        .order_by(ProjectInvitation.created_at.desc(), ProjectInvitation.id.desc())
    )
    return [(inv, name) for inv, name in rows]


def get_live_in_project(db: Session, project_id: int, invitation_id: int, now: datetime) -> ProjectInvitation | None:
    return db.scalar(
        select(ProjectInvitation).where(
            ProjectInvitation.project_id == project_id, ProjectInvitation.id == invitation_id, *_live(now)
        )
    )


def get_live_by_token_hash(
    db: Session, token_hash: str, now: datetime, *, for_update: bool = False
) -> ProjectInvitation | None:
    stmt = select(ProjectInvitation).where(ProjectInvitation.token_hash == token_hash, *_live(now))
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_user_by_email(db: Session, email: str) -> User | None:
    # 킷은 이메일을 소문자로 저장합니다 (users.service)
    return db.scalar(select(User).where(User.email == email))


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def add(db: Session, row: ProjectInvitation) -> None:
    db.add(row)
    db.flush()

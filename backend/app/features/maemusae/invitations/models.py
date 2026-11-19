"""프로젝트 초대 테이블.

    mms_projects ──< mms_project_invitations      이메일로 보낸 초대 (수락하면 mms_project_members 한 행)

링크 토큰의 원문은 메일에만 있고 DB에는 HMAC 해시(token_hash)만 둡니다. 7일 뒤 만료, 한 번만 쓰고,
같은 이메일로 다시 초대하면 이전 초대는 revoked_at 으로 무효가 됩니다.

이메일 암호화 (계획 23): `inv.email` 은 암호화 칸(email_enc, 읽으면 평문)입니다. 평문 칸은 없습니다 (M2 에서 삭제).
암호화 칸은 WHERE 에 쓸 수 없어(TypeError) 찾기는 지문 email_hash 로 합니다. 저장할 때 아래 이벤트가 지문을 채웁니다.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto import EncryptedString, email_index

INVITE_EXPIRE_DAYS = 7


class ProjectInvitation(Base):
    __tablename__ = "mms_project_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'MEMBER')", name="ck_mms_project_invitations_role"),
        # 같은 프로젝트·이메일에 살아 있는(수락·취소 전) 초대는 하나만
        Index(
            "uq_mms_project_invitations_live",
            "project_id",
            "email_hash",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("mms_projects.id", ondelete="CASCADE"))
    # 초대받는 이메일 (소문자). DB 칸은 email_enc(암호문). 괄호 안 문자열(aad)은 바꾸지 않습니다
    email: Mapped[str] = mapped_column("email_enc", EncryptedString("mms_project_invitations.email"))
    email_hash: Mapped[str] = mapped_column(String(64), index=True)  # 이메일 지문. 찾기는 이 칸으로
    role: Mapped[str] = mapped_column(String(20))  # 수락하면 받을 프로젝트 역할
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 취소 또는 다시 초대
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def fill_email_pii(inv: ProjectInvitation) -> None:
    inv.email_hash = email_index(inv.email)


@event.listens_for(ProjectInvitation, "before_insert")
def _fill_email_pii_on_insert(mapper, connection, inv: ProjectInvitation) -> None:
    fill_email_pii(inv)


@event.listens_for(ProjectInvitation, "before_update")
def _fill_email_pii_on_update(mapper, connection, inv: ProjectInvitation) -> None:
    if inspect(inv).attrs.email.history.has_changes():
        fill_email_pii(inv)

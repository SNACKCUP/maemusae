"""프로젝트 초대 테이블.

    mms_projects ──< mms_project_invitations      이메일로 보낸 초대 (수락하면 mms_project_members 한 행)

링크 토큰의 원문은 메일에만 있고 DB에는 HMAC 해시(token_hash)만 둡니다. 7일 뒤 만료, 한 번만 쓰고,
같은 이메일로 다시 초대하면 이전 초대는 revoked_at 으로 무효가 됩니다.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

INVITE_EXPIRE_DAYS = 7


class ProjectInvitation(Base):
    __tablename__ = "mms_project_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'MEMBER')", name="ck_mms_project_invitations_role"),
        # 같은 프로젝트·이메일에 살아 있는(수락·취소 전) 초대는 하나만
        Index(
            "uq_mms_project_invitations_live",
            "project_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("mms_projects.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(255), index=True)  # 소문자로 저장
    role: Mapped[str] = mapped_column(String(20))  # 수락하면 받을 프로젝트 역할
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 취소 또는 다시 초대
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

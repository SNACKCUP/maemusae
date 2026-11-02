"""프로젝트·멤버 테이블 (JPA의 @Entity 모음).

    mms_projects ──< mms_project_members >── users      프로젝트 ↔ 회원 (다대다, 역할 포함)
    mms_project_invitations ──o mms_project_members     초대를 수락하면 멤버 (invitation_id)

프로젝트 안 권한(ADMIN 관리자 / MEMBER 일반)은 이 테이블의 role 로 정합니다. 킷 역할(MASTER 등)과 별개입니다.
role 은 코드가 흐름을 바꾸는 값이라 공통코드가 아니라 CHECK 로 둡니다.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin

ADMIN = "ADMIN"  # 프로젝트 관리자: 수정·삭제·멤버 관리·확정
MEMBER = "MEMBER"  # 일반 멤버: 보기·올리기·분석·입력
PROJECT_ROLES = (ADMIN, MEMBER)


class Project(TimestampMixin, Base):
    __tablename__ = "mms_projects"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_mms_projects_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # 프로젝트명 (검색 대상)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))  # 만든 사람 (첫 관리자)
    # 삭제하면 먼저 표시만 합니다. 보관 기간 뒤 정리 명령이 실제로 지웁니다 (매무새 M4)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectMember(TimestampMixin, Base):
    __tablename__ = "mms_project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_mms_project_members_project_user"),
        CheckConstraint("role IN ('ADMIN', 'MEMBER')", name="ck_mms_project_members_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # (project_id, user_id) UNIQUE 가 project_id 로 찾는 인덱스 역할도 합니다
    project_id: Mapped[int] = mapped_column(ForeignKey("mms_projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 내 프로젝트 목록
    role: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # 만든 때 또는 초대 수락 때
    # 초대로 들어왔으면 그 초대 (만든 사람은 비움). 초대 테이블은 invitations/models.py
    invitation_id: Mapped[int | None] = mapped_column(
        ForeignKey("mms_project_invitations.id", ondelete="SET NULL", name="fk_mms_project_members_invitation_id")
    )

"""프로젝트·멤버 업무 규칙. 권한 검사는 access.py 가 끝낸 뒤에 불립니다.

- 만든 사람이 첫 관리자, 요구사항정의서 문서 1행도 같이 만듦
- 프로젝트에는 관리자가 한 명 이상 남아야 함 (강등·내보내기·나가기 모두). 같은 프로젝트의 멤버 변경이 동시에
  일어나도 어긋나지 않도록 프로젝트 행을 잠근 뒤 셉니다
- 삭제는 표시만 (deleted_at). 표시된 프로젝트는 모든 API 에서 없는 것으로 봅니다
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.documents.service import create_initial_documents
from app.features.maemusae.errors import (
    InvalidPeriodError,
    LastProjectAdminError,
    MemberNotFoundError,
    ProjectAdminRequiredError,
    ProjectNotFoundError,
)
from app.features.maemusae.projects import repository
from app.features.maemusae.projects.models import ADMIN, Project, ProjectMember
from app.features.maemusae.projects.schemas import (
    MemberRead,
    ProjectCreate,
    ProjectPage,
    ProjectRead,
)
from app.users.models import User

logger = logging.getLogger(__name__)


def _read(db: Session, project: Project, my_role: str | None, member_count: int | None = None) -> ProjectRead:
    if member_count is None:
        member_count = repository.count_members(db, project.id)
    return ProjectRead(
        id=project.id,
        name=project.name,
        start_date=project.start_date,
        end_date=project.end_date,
        member_count=member_count,
        my_role=my_role,
        created_at=project.created_at,
    )


def create_project(db: Session, actor_id: int, body: ProjectCreate) -> ProjectRead:
    project = Project(name=body.name, start_date=body.start_date, end_date=body.end_date, created_by=actor_id)
    repository.add(db, project)
    repository.add(db, ProjectMember(project_id=project.id, user_id=actor_id, role=ADMIN))
    create_initial_documents(db, project.id)
    db.commit()
    db.refresh(project)
    logger.info("프로젝트 생성 project_id=%s actor_id=%s", project.id, actor_id)
    return _read(db, project, ADMIN, member_count=1)


def list_my_projects(db: Session, actor_id: int, *, q: str | None, page: int, size: int) -> ProjectPage:
    rows, total = repository.search_my_projects(db, actor_id, q=q, offset=(page - 1) * size, limit=size)
    items = [_read(db, project, role, count) for project, role, count in rows]
    return ProjectPage(items=items, total=total, page=page, size=size)


def get_project(db: Session, access: ProjectAccess) -> ProjectRead:
    return _read(db, access.project, access.role)


def update_project(db: Session, access: ProjectAccess, changes: dict) -> ProjectRead:
    project = access.project
    start = changes.get("start_date", project.start_date)
    end = changes.get("end_date", project.end_date)
    if end < start:
        raise InvalidPeriodError()
    for field in ("name", "start_date", "end_date"):
        if field in changes:
            setattr(project, field, changes[field])
    db.commit()
    db.refresh(project)
    logger.info(
        "프로젝트 수정 project_id=%s fields=%s actor_id=%s", project.id, sorted(changes), access.principal.user_id
    )
    return _read(db, project, access.role)


def delete_project(db: Session, access: ProjectAccess) -> None:
    access.project.deleted_at = datetime.now(UTC)
    db.commit()
    logger.info("프로젝트 삭제 표시 project_id=%s actor_id=%s", access.project.id, access.principal.user_id)


# ---- 멤버 ----


def _member_read(member: ProjectMember, user: User) -> MemberRead:
    return MemberRead(id=member.id, user_id=user.login_id, name=user.name, role=member.role, joined_at=member.joined_at)


def list_members(db: Session, access: ProjectAccess) -> list[MemberRead]:
    return [_member_read(m, u) for m, u in repository.list_members(db, access.project.id)]


def _lock_and_get_member(db: Session, project_id: int, member_id: int) -> ProjectMember:
    # 프로젝트 행을 잠가, 관리자 두 명이 서로를 동시에 강등해 관리자가 0명이 되는 일을 막습니다
    if repository.get_live_project(db, project_id, for_update=True) is None:
        raise ProjectNotFoundError()
    member = repository.get_member(db, project_id, member_id)
    if member is None:
        raise MemberNotFoundError()
    return member


def _ensure_not_last_admin(db: Session, member: ProjectMember) -> None:
    if member.role == ADMIN and repository.count_admins(db, member.project_id) <= 1:
        raise LastProjectAdminError()


def change_member_role(db: Session, access: ProjectAccess, member_id: int, role: str) -> MemberRead:
    member = _lock_and_get_member(db, access.project.id, member_id)
    if member.role != role:
        if role != ADMIN:
            _ensure_not_last_admin(db, member)
        member.role = role
        db.commit()
        logger.info(
            "프로젝트 멤버 역할 변경 project_id=%s member_id=%s role=%s actor_id=%s",
            access.project.id, member_id, role, access.principal.user_id,
        )
    return _member_read(member, repository.get_user(db, member.user_id))


def remove_member(db: Session, access: ProjectAccess, member_id: int) -> None:
    """관리자는 누구든 내보낼 수 있고, 일반 멤버는 자기 자신만(나가기) 뺄 수 있습니다."""
    member = _lock_and_get_member(db, access.project.id, member_id)
    is_self = member.user_id == access.principal.user_id
    if not is_self and access.role != ADMIN:
        raise ProjectAdminRequiredError()
    _ensure_not_last_admin(db, member)
    repository.delete_member(db, member)
    db.commit()
    logger.info(
        "프로젝트 멤버 %s project_id=%s member_id=%s actor_id=%s",
        "나가기" if is_self else "내보내기", access.project.id, member_id, access.principal.user_id,
    )

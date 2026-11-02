"""프로젝트·멤버 테이블 접근 (Spring의 Repository/DAO 역할). SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.maemusae.projects.models import ADMIN, Project, ProjectMember
from app.users.models import User


def _like(q: str) -> str:
    """검색어를 "포함" 검색용 패턴으로. 사용자가 넣은 % _ 는 글자 그대로 찾도록 막습니다."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def get_live_project(db: Session, project_id: int, *, for_update: bool = False) -> Project | None:
    """삭제 표시가 없는 프로젝트. for_update=True 면 행을 잠가 같은 프로젝트의 멤버 변경이 겹치지 않게 합니다."""
    stmt = select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_member_of_user(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )


def get_member(db: Session, project_id: int, member_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.id == member_id)
    )


def count_members(db: Session, project_id: int) -> int:
    return db.scalar(select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id))


def count_admins(db: Session, project_id: int) -> int:
    return db.scalar(
        select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id, ProjectMember.role == ADMIN)
    )


def search_my_projects(
    db: Session, user_id: int, *, q: str | None, offset: int, limit: int
) -> tuple[list[tuple[Project, str, int]], int]:
    """내가 속한 프로젝트 (프로젝트, 내 역할, 멤버 수) 목록과 전체 개수. 최근 만든 순"""
    member_count = (
        select(func.count(ProjectMember.id))
        .where(ProjectMember.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    stmt = (
        select(Project, ProjectMember.role, member_count)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id, Project.deleted_at.is_(None))
    )
    if q:
        stmt = stmt.where(Project.name.ilike(_like(q), escape="\\"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Project.created_at.desc(), Project.id.desc()).offset(offset).limit(limit))
    return [(project, role, count) for project, role, count in rows], total


def list_members(db: Session, project_id: int) -> list[tuple[ProjectMember, User]]:
    """멤버와 회원 정보. 관리자 먼저, 그다음 참여한 순"""
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by((ProjectMember.role == ADMIN).desc(), ProjectMember.joined_at, ProjectMember.id)
    )
    return [(member, user) for member, user in rows]


def get_user(db: Session, user_id: int) -> User:
    return db.get(User, user_id)


def add(db: Session, row: Project | ProjectMember) -> None:
    db.add(row)
    db.flush()


def delete_member(db: Session, member: ProjectMember) -> None:
    db.delete(member)
    db.flush()

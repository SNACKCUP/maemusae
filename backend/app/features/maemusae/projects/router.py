"""매무새 프로젝트·멤버 API: /api/mms/projects (모두 로그인 필요).

누가 무엇을 할 수 있는지는 access.py 의 표와 같습니다. 멤버가 아니면 프로젝트가 있는지조차 알리지 않도록 404 입니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, require_login
from app.features.maemusae.access import (
    ProjectAccess,
    project_admin,
    project_member,
    project_viewer,
)
from app.features.maemusae.projects import service
from app.features.maemusae.projects.schemas import (
    MemberRead,
    MemberRoleUpdate,
    ProjectCreate,
    ProjectPage,
    ProjectRead,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["mms-projects"], dependencies=[Depends(require_login)])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, summary="프로젝트 만들기 (만든 사람이 관리자)")
def create_project(
    body: ProjectCreate, principal: Principal = Depends(require_login), db: Session = Depends(get_db)
):
    return service.create_project(db, principal.user_id, body)


@router.get("", response_model=ProjectPage, summary="내가 속한 프로젝트 목록 (이름 검색, 최근 만든 순)")
def list_my_projects(
    q: Annotated[str | None, Query(max_length=100, description="프로젝트명에 포함된 글자")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    principal: Principal = Depends(require_login),
    db: Session = Depends(get_db),
):
    return service.list_my_projects(db, principal.user_id, q=q, page=page, size=size)


@router.get("/{project_id}", response_model=ProjectRead, summary="프로젝트 상세 (멤버, 또는 MASTER 보기만)")
def get_project(access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.get_project(db, access)


@router.patch("/{project_id}", response_model=ProjectRead, summary="프로젝트 수정 (프로젝트 관리자)")
def update_project(
    body: ProjectUpdate, access: ProjectAccess = Depends(project_admin), db: Session = Depends(get_db)
):
    return service.update_project(db, access, body.model_dump(exclude_unset=True))


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
    summary="프로젝트 삭제 (프로젝트 관리자, 삭제 표시)",
)
def delete_project(access: ProjectAccess = Depends(project_admin), db: Session = Depends(get_db)):
    service.delete_project(db, access)


@router.get("/{project_id}/members", response_model=list[MemberRead], summary="멤버 목록 (멤버, 또는 MASTER 보기만)")
def list_members(access: ProjectAccess = Depends(project_viewer), db: Session = Depends(get_db)):
    return service.list_members(db, access)


@router.patch(
    "/{project_id}/members/{member_id}", response_model=MemberRead, summary="멤버 역할 변경 (프로젝트 관리자)"
)
def change_member_role(
    member_id: int,
    body: MemberRoleUpdate,
    access: ProjectAccess = Depends(project_admin),
    db: Session = Depends(get_db),
):
    return service.change_member_role(db, access, member_id, body.role)


@router.delete(
    "/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
    summary="멤버 내보내기 (프로젝트 관리자) · 나가기 (본인)",
)
def remove_member(member_id: int, access: ProjectAccess = Depends(project_member), db: Session = Depends(get_db)):
    service.remove_member(db, access, member_id)

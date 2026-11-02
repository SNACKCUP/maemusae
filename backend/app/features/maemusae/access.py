"""프로젝트 접근 검사. 매무새의 모든 프로젝트 API 가 경로의 {project_id} 로 이 함수 중 하나를 씁니다.

    @router.patch("/projects/{project_id}")
    def update(access: ProjectAccess = Depends(project_admin)): ...

| 함수            | 통과                                     | 아니면                                       |
| project_viewer  | 프로젝트 멤버, 또는 서비스 MASTER(보기만) | 404 PROJECT_NOT_FOUND                        |
| project_member  | 프로젝트 멤버                            | 404                                          |
| project_admin   | 프로젝트 관리자                          | 멤버면 403 PROJECT_ADMIN_REQUIRED, 아니면 404 |

로그인 확인은 킷의 require_login 이 하고(없으면 401), 프로젝트 역할은 요청마다 DB 에서 읽습니다.
킷 MASTER 검사와 프로젝트 역할 검사는 섞지 않습니다: MASTER 는 멤버가 아니면 보기만 할 수 있고(고객 지원용),
쓰기 API 는 project_member / project_admin 만 쓰므로 MASTER 라도 막힙니다.
"""

import logging
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import ADMIN_ROLE, Principal, require_login
from app.features.maemusae.errors import ProjectAdminRequiredError, ProjectNotFoundError
from app.features.maemusae.projects import repository
from app.features.maemusae.projects.models import ADMIN, Project, ProjectMember

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    principal: Principal
    member: ProjectMember | None  # MASTER 가 보기만 할 때는 None

    @property
    def role(self) -> str | None:
        return self.member.role if self.member else None


def _load(db: Session, project_id: int, principal: Principal) -> tuple[Project, ProjectMember | None]:
    project = repository.get_live_project(db, project_id)
    if project is None:
        raise ProjectNotFoundError()
    return project, repository.get_member_of_user(db, project_id, principal.user_id)


def project_viewer(
    project_id: int, principal: Principal = Depends(require_login), db: Session = Depends(get_db)
) -> ProjectAccess:
    project, member = _load(db, project_id, principal)
    if member is None:
        if ADMIN_ROLE not in principal.roles:
            raise ProjectNotFoundError()
        # 고객 프로젝트 열람 기록. 누가 어느 프로젝트를 봤는지 id 만 남기고 내용은 남기지 않습니다
        logger.info("MASTER 프로젝트 열람 project_id=%s actor_id=%s", project_id, principal.user_id)
    return ProjectAccess(project, principal, member)


def project_member(
    project_id: int, principal: Principal = Depends(require_login), db: Session = Depends(get_db)
) -> ProjectAccess:
    project, member = _load(db, project_id, principal)
    if member is None:
        raise ProjectNotFoundError()
    return ProjectAccess(project, principal, member)


def project_admin(access: ProjectAccess = Depends(project_member)) -> ProjectAccess:
    if access.role != ADMIN:
        raise ProjectAdminRequiredError()
    return access

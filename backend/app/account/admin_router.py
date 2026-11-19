"""관리자 회원 API: /api/users (멤버 검색·역할 부여·활성/비활성·삭제), /api/users/roles"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.core.principal import require_admin
from app.users import service
from app.users.models import User
from app.users.schemas import (
    ActiveUpdate,
    MemberStatus,
    RoleRead,
    RolesUpdate,
    UserPage,
    UserRead,
)

router = APIRouter(prefix="/users", tags=["users (admin)"])


@router.get(
    "",
    response_model=UserPage,
    dependencies=[Depends(require_admin)],
    summary="멤버 검색 (아이디·이름·닉네임 포함 검색, 이메일은 전체 주소로 정확히, 역할·상태 필터, 페이지)",
    description="q 에 @ 가 있으면 이메일 전체 주소와 정확히 같은 회원만 찾습니다 (이메일은 암호화되어 부분 검색 불가). "
    "목록의 이메일은 가려서 보내고, 전체 주소는 GET /users/{user_id} 로 봅니다.",
)
def list_users(
    q: Annotated[str | None, Query(max_length=100)] = None,
    role_id: int | None = None,
    status: MemberStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
):
    items, total = service.search_users(
        db, q=q, role_id=role_id, status=status, page=page, size=size
    )
    return UserPage(items=items, total=total, page=page, size=size)


@router.get("/roles", response_model=list[RoleRead], summary="역할 목록")
def list_roles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return service.list_roles(db)


@router.get(
    "/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)], summary="멤버 한 명 (이메일 전체)"
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return service.get_user_for_admin(db, user_id)


@router.put("/{user_id}/roles", response_model=UserRead, dependencies=[Depends(require_admin)], summary="역할 변경")
def update_roles(
    user_id: int,
    body: RolesUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    return service.update_roles(db, admin, user_id, body.roles)


@router.patch(
    "/{user_id}/active", response_model=UserRead, dependencies=[Depends(require_admin)], summary="활성/비활성"
)
def update_active(
    user_id: int,
    body: ActiveUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    return service.update_active(db, admin, user_id, body.is_active)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="멤버 삭제 (탈퇴 처리, 보관 기간 뒤 개인정보 삭제)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
):
    service.delete_user(db, admin, user_id)

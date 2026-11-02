"""매무새 초대 API.

    /api/mms/projects/{project_id}/invitations   관리자: 보내기·대기 목록·취소
    /api/mms/invitations/lookup|signup-proof      링크를 가진 사람 (로그인 없이, 토큰은 본문으로)
    /api/mms/invitations/accept                   로그인 + 초대 이메일과 같은 계정

토큰을 주소에 넣으면 요청 로그에 남으므로 링크 API 는 모두 POST 본문으로 받습니다.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, require_login
from app.features.maemusae.access import ProjectAccess, project_admin
from app.features.maemusae.invitations import service
from app.features.maemusae.invitations.schemas import (
    InvitationAccepted,
    InvitationCreate,
    InvitationInfo,
    InvitationRead,
    InvitationSignupProof,
    InvitationTokenBody,
)

project_router = APIRouter(prefix="/projects/{project_id}/invitations", tags=["mms-invitations"])
link_router = APIRouter(prefix="/invitations", tags=["mms-invitations"])


@project_router.post(
    "", response_model=InvitationRead, status_code=status.HTTP_201_CREATED,
    summary="초대 보내기 (프로젝트 관리자, 메일 발송)",
)
def invite(
    body: InvitationCreate,
    tasks: BackgroundTasks,
    access: ProjectAccess = Depends(project_admin),
    db: Session = Depends(get_db),
):
    return service.invite(db, tasks, access, body.email, body.role)


@project_router.get("", response_model=list[InvitationRead], summary="대기 중인 초대 목록 (프로젝트 관리자)")
def list_pending(access: ProjectAccess = Depends(project_admin), db: Session = Depends(get_db)):
    return service.list_pending(db, access)


@project_router.delete(
    "/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
    summary="초대 취소 (프로젝트 관리자)",
)
def revoke(invitation_id: int, access: ProjectAccess = Depends(project_admin), db: Session = Depends(get_db)):
    service.revoke(db, access, invitation_id)


@link_router.post("/lookup", response_model=InvitationInfo, summary="초대 링크 내용 보기 (로그인 없이)")
def lookup(body: InvitationTokenBody, db: Session = Depends(get_db)):
    return service.lookup(db, body.token)


@link_router.post(
    "/signup-proof", response_model=InvitationSignupProof,
    summary="초대 링크로 가입할 때 쓰는 가입 증표 받기 (로그인 없이, 인증번호 생략)",
)
def signup_proof(body: InvitationTokenBody, db: Session = Depends(get_db)):
    return service.signup_proof(db, body.token)


@link_router.post("/accept", response_model=InvitationAccepted, summary="초대 수락 (로그인, 초대 이메일과 같은 계정)")
def accept(body: InvitationTokenBody, principal: Principal = Depends(require_login), db: Session = Depends(get_db)):
    return service.accept(db, body.token, principal)

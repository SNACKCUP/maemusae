"""초대 업무 규칙. 관리자 API 는 access.py 의 project_admin 검사 뒤에, 링크 API 는 토큰만으로 불립니다.

흐름 (09 결정 3):
    관리자가 초대 → 메일 링크(토큰 원문) → 링크 열기(lookup)
      ├ 가입 전: signup_proof 로 킷 가입 증표 받기(인증번호 생략) → 킷 /auth/signup(이메일 고정) → 로그인
      └ 가입함: 로그인
    → accept: 로그인한 계정의 이메일이 초대 이메일과 같아야 멤버가 됨. 토큰은 한 번만

- 토큰 원문은 메일에만, DB에는 hash_secret 결과만. 로그에는 초대 id 만 (토큰·이메일 X)
- 없는·만료·취소·사용된 토큰은 모두 같은 404 INVITATION_INVALID
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.auth.service import issue_verified_email_proof
from app.core.config import settings
from app.core.principal import Principal
from app.core.security import generate_token, hash_secret
from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.errors import (
    AlreadyMemberError,
    InvitationEmailMismatchError,
    InvitationInvalidError,
    InvitationNotFoundError,
    ProjectNotFoundError,
)
from app.features.maemusae.invitations import mail, repository
from app.features.maemusae.invitations.models import (
    INVITE_EXPIRE_DAYS,
    ProjectInvitation,
)
from app.features.maemusae.invitations.schemas import (
    InvitationAccepted,
    InvitationInfo,
    InvitationRead,
    InvitationSignupProof,
)
from app.features.maemusae.projects import repository as project_repository
from app.features.maemusae.projects.models import ProjectMember
from app.mail import send_mail

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _read(inv: ProjectInvitation, inviter_name: str) -> InvitationRead:
    return InvitationRead(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        invited_by_name=inviter_name,
        expires_at=inv.expires_at,
        created_at=inv.created_at,
    )


def invite(db: Session, tasks: BackgroundTasks, access: ProjectAccess, email: str, role: str) -> InvitationRead:
    email = email.strip().lower()
    project_id = access.project.id
    # 프로젝트 행을 잠가 같은 이메일 초대가 동시에 두 번 들어와도 살아 있는 초대가 하나만 남게 합니다
    project = project_repository.get_live_project(db, project_id, for_update=True)
    if project is None:
        raise ProjectNotFoundError()
    user = repository.get_user_by_email(db, email)
    if user is not None and project_repository.get_member_of_user(db, project_id, user.id) is not None:
        raise AlreadyMemberError()

    now = _now()
    repository.revoke_live(db, project_id, email, now)  # 다시 초대하면 이전 링크는 무효
    raw = generate_token()
    inv = ProjectInvitation(
        project_id=project_id,
        email=email,
        role=role,
        token_hash=hash_secret(raw),
        invited_by=access.principal.user_id,
        expires_at=now + timedelta(days=INVITE_EXPIRE_DAYS),
    )
    repository.add(db, inv)
    db.commit()
    db.refresh(inv)

    inviter = repository.get_user(db, access.principal.user_id)
    link = f"{settings.frontend_base_url.rstrip('/')}/maemusae/invite?token={raw}"
    tasks.add_task(
        send_mail,
        email,
        mail.TEMPLATE,
        {
            "project_name": project.name,
            "inviter_name": inviter.name,
            "role": role,
            "link": link,
            "expire_days": INVITE_EXPIRE_DAYS,
        },
    )
    logger.info("프로젝트 초대 project_id=%s invitation_id=%s actor_id=%s", project_id, inv.id, access.principal.user_id)
    return _read(inv, inviter.name)


def list_pending(db: Session, access: ProjectAccess) -> list[InvitationRead]:
    return [_read(inv, name) for inv, name in repository.list_live(db, access.project.id, _now())]


def revoke(db: Session, access: ProjectAccess, invitation_id: int) -> None:
    now = _now()
    inv = repository.get_live_in_project(db, access.project.id, invitation_id, now)
    if inv is None:
        raise InvitationNotFoundError()
    inv.revoked_at = now
    db.commit()
    logger.info(
        "프로젝트 초대 취소 project_id=%s invitation_id=%s actor_id=%s",
        access.project.id, invitation_id, access.principal.user_id,
    )


# ---- 링크를 가진 사람 ----


def _valid(db: Session, token: str, *, for_update: bool = False) -> ProjectInvitation:
    inv = repository.get_live_by_token_hash(db, hash_secret(token), _now(), for_update=for_update)
    # 프로젝트가 삭제 표시되었으면 초대도 쓸 수 없습니다
    if inv is None or project_repository.get_live_project(db, inv.project_id) is None:
        raise InvitationInvalidError()
    return inv


def lookup(db: Session, token: str) -> InvitationInfo:
    inv = _valid(db, token)
    project = project_repository.get_live_project(db, inv.project_id)
    inviter = repository.get_user(db, inv.invited_by)
    return InvitationInfo(
        project_name=project.name,
        invited_by_name=inviter.name,
        role=inv.role,
        email=inv.email,
        expires_at=inv.expires_at,
        account_exists=repository.get_user_by_email(db, inv.email) is not None,
    )


def signup_proof(db: Session, token: str) -> InvitationSignupProof:
    """초대 토큰이 그 메일함으로만 갔으므로 메일함 소유 확인으로 보고, 킷 가입 증표를 받습니다 (인증번호 생략).

    증표는 초대 이메일에만 나오고 킷 가입 API 가 증표의 이메일과 가입 이메일을 비교하므로, 다른 이메일로는 가입할 수 없습니다.
    이미 가입한 이메일이면 킷이 409 EMAIL_TAKEN 을 줍니다 (로그인 후 수락하면 됨).
    """
    inv = _valid(db, token)
    proof = issue_verified_email_proof(db, inv.email)
    logger.info("초대 링크 가입 증표 발급 invitation_id=%s", inv.id)
    return InvitationSignupProof(email=inv.email, email_verification_token=proof)


def accept(db: Session, token: str, principal: Principal) -> InvitationAccepted:
    # 초대 행을 잠가 같은 토큰으로 두 번 수락하는 요청이 겹쳐도 한 번만 처리합니다
    inv = _valid(db, token, for_update=True)
    user = repository.get_user(db, principal.user_id)
    if user is None or user.email != inv.email:
        raise InvitationEmailMismatchError()

    now = _now()
    member = project_repository.get_member_of_user(db, inv.project_id, user.id)
    if member is None:
        member = ProjectMember(project_id=inv.project_id, user_id=user.id, role=inv.role, invitation_id=inv.id)
        project_repository.add(db, member)
    inv.accepted_at = now
    inv.accepted_user_id = user.id
    db.commit()
    logger.info("프로젝트 초대 수락 project_id=%s invitation_id=%s actor_id=%s", inv.project_id, inv.id, user.id)
    return InvitationAccepted(project_id=inv.project_id, role=member.role)

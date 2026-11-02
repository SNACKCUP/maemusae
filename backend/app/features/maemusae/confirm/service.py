"""요구사항 확정·확정 후 수정·확정한 문서·Excel (M4-1, 계획 19). 권한 검사(보기)는 access.py 가 끝낸 뒤에 불립니다.

- 확정·다시 열기는 프로젝트 관리자만 (09 6장). 일반 멤버 403 PROJECT_ADMIN_REQUIRED, 보기 전용 MASTER 403 PROJECT_MEMBER_REQUIRED
- 확정은 READY 문서에서만. 체크된 후보만 버전 기록과 같은 모양(후보·근거·입력)으로 mms_document_versions 에
  CONFIRMED 로 복사하고 문서를 CONFIRMED 로. 요청 한 번에 끝나므로 CONFIRMING 은 거치지 않음 (문서 행 배타 잠금)
- AI 질문·AI 값 확인이 남아 있어도 막지 않음. 화면이 문서 응답의 개수로 미리 경고 (08·09 결정)
- 다시 열기는 문서만 READY 로. 확정 기록은 그대로 두고 다음 확정이 revision + 1 ("수정 후 확정")
- Excel 은 확정 기록에서만 만들고, 고객 문서라 멤버만 받음 (MASTER 403)

로그에는 id·확정 번호·후보 수만 남기고 내용은 남기지 않습니다.
"""

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.codes import list_codes
from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.confirm import repository
from app.features.maemusae.confirm.excel import SheetMeta, build_requirements_xlsx
from app.features.maemusae.confirm.schemas import ConfirmedDocument, ConfirmResult
from app.features.maemusae.documents.models import (
    BUSY_STATUSES,
    CONFIRMED,
    READY,
    Document,
)
from app.features.maemusae.errors import (
    ConfirmedVersionNotFoundError,
    DocumentBusyError,
    DocumentConfirmedError,
    DocumentNotConfirmedError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    NothingToConfirmError,
    ProjectAdminRequiredError,
    ProjectMemberRequiredError,
)
from app.features.maemusae.projects.models import ADMIN
from app.features.maemusae.review import repository as review_repository
from app.features.maemusae.review.service import (
    KIND_GROUP,
    PRIORITY_GROUP,
    get_document,
)
from app.features.maemusae.versions import repository as versions_repository
from app.features.maemusae.versions import service as versions_service
from app.features.maemusae.versions.models import CONFIRMED as CONFIRMED_VERSION
from app.features.maemusae.versions.models import DocumentVersion

logger = logging.getLogger(__name__)

DOC_KIND_GROUP = "MMS_DOC_KIND"
_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _require_admin(access: ProjectAccess) -> None:
    if access.member is None:  # 보기 전용 MASTER
        raise ProjectMemberRequiredError()
    if access.role != ADMIN:
        raise ProjectAdminRequiredError()


def _lock(db: Session, access: ProjectAccess, document_id: int) -> Document:
    document = review_repository.lock_document(db, access.project.id, document_id, exclusive=True)
    if document is None:
        raise DocumentNotFoundError()
    return document


def confirm(db: Session, access: ProjectAccess, document_id: int) -> ConfirmResult:
    _require_admin(access)
    document = _lock(db, access, document_id)
    if document.status == CONFIRMED:
        raise DocumentConfirmedError()
    if document.status in BUSY_STATUSES:
        raise DocumentBusyError()
    if document.status != READY:
        raise DocumentNotReadyError()
    items = [item for item in versions_service.snapshot(db, document.id) if item["is_included"]]
    if not items:
        raise NothingToConfirmError()

    actor_id = access.principal.user_id
    now = db.scalar(select(func.now()))
    revision = repository.last_revision(db, document.id) + 1
    version = DocumentVersion(
        document_id=document.id,
        kind=CONFIRMED_VERSION,
        revision=revision,
        title=versions_service.TITLE,
        item_count=len(items),
        items=items,
        created_by=actor_id,
    )
    versions_repository.add(db, version)
    repository.clear_defaulted(db, document.id)
    document.status = CONFIRMED
    document.current_revision = revision
    document.confirmed_at = now
    document.confirmed_by = actor_id
    db.commit()
    logger.info(
        "요구사항 확정 document_id=%s version_id=%s revision=%s items=%s actor_id=%s",
        document.id, version.id, revision, len(items), actor_id,
    )
    return ConfirmResult(version_id=version.id, revision=revision, item_count=len(items), confirmed_at=now)


def reopen(db: Session, access: ProjectAccess, document_id: int) -> None:
    _require_admin(access)
    document = _lock(db, access, document_id)
    if document.status != CONFIRMED:
        raise DocumentNotConfirmedError()
    document.status = READY
    db.commit()
    logger.info(
        "요구사항 확정 후 수정 document_id=%s revision=%s actor_id=%s",
        document.id, document.current_revision, access.principal.user_id,
    )


def warning_counts(db: Session, document: Document) -> dict:
    """문서 응답에 더하는 확정 창 경고 개수"""
    open_questions, defaulted = repository.warning_counts(db, document.id)
    return {"open_question_count": open_questions, "defaulted_count": defaulted}


def _labels(db: Session, group: str) -> dict[str, str]:
    # 꺼진 값도 이미 저장된 후보의 이름은 보여야 하므로 include_inactive
    return {code.code: code.label for code in list_codes(db, group, include_inactive=True)}


def list_confirmed(db: Session, access: ProjectAccess) -> list[ConfirmedDocument]:
    kinds = _labels(db, DOC_KIND_GROUP)
    return [
        ConfirmedDocument(
            version_id=version.id,
            document_id=version.document_id,
            title=version.title,
            kind=kind,
            kind_label=kinds.get(kind, kind),
            revision=version.revision,
            item_count=version.item_count,
            confirmed_by_name=name,
            confirmed_at=version.created_at,
        )
        for version, kind, name in repository.list_confirmed(db, access.project.id)
    ]


def build_excel(db: Session, access: ProjectAccess, document_id: int, version_id: int) -> tuple[str, bytes]:
    """(파일 이름, xlsx 내용)"""
    if access.member is None:  # 고객 문서를 밖으로 가져가지 않음 (09 6장)
        raise ProjectMemberRequiredError()
    document = get_document(db, access, document_id)
    row = repository.get_confirmed(db, document.id, version_id)
    if row is None:
        raise ConfirmedVersionNotFoundError()
    version, confirmed_by = row
    kinds, priorities = _labels(db, KIND_GROUP), _labels(db, PRIORITY_GROUP)
    meta = SheetMeta(
        project_name=access.project.name,
        title=version.title,
        revision=version.revision,
        confirmed_at=version.created_at,
        confirmed_by=confirmed_by,
    )
    data = build_requirements_xlsx(meta, version.items, lambda c: kinds.get(c, c), lambda c: priorities.get(c, c))
    logger.info(
        "요구사항정의서 Excel document_id=%s version_id=%s items=%s actor_id=%s",
        document.id, version.id, version.item_count, access.principal.user_id,
    )
    name = _UNSAFE_FILENAME.sub("_", access.project.name).strip() or "project"
    return f"{name}_{version.title}_확정{version.revision}.xlsx", data

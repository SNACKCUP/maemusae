"""문서·올린 파일 업무 규칙. 권한 검사(보기·멤버)는 access.py 가 끝낸 뒤에 불립니다.

올리기 순서: 크기 확인 → 형식 확인·마크다운 변환(쪽 나누기) → 문서 잠금 → 파일 수·중복 확인
→ 원본을 비공개 저장소에 올림 → DB 저장. DB 저장이 실패하면 올린 원본을 지웁니다.
지우기 순서: DB 먼저 지우고 원본 삭제. 원본 삭제가 실패하면 로그만 남깁니다 (DB 에는 없으므로 아무도 못 받음).

로그에는 id·크기·쪽 수·걸린 시간만 남깁니다. 파일 이름·본문은 고객 정보라 남기지 않습니다.
"""

import hashlib
import logging
import time
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.codes import list_codes
from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.config import mms_settings
from app.features.maemusae.confirm import service as confirm_service
from app.features.maemusae.documents import parsing, repository
from app.features.maemusae.documents.models import (
    BUSY_STATUSES,
    FILE,
    REQUIREMENTS,
    TEXT,
    Document,
    SourceFile,
    SourcePage,
)
from app.features.maemusae.documents.schemas import (
    DocumentRead,
    SourcePageRead,
    SourceRead,
)
from app.features.maemusae.errors import (
    DocumentBusyError,
    DocumentNotFoundError,
    FileTooLargeError,
    SourceDeleteForbiddenError,
    SourceDuplicateError,
    SourceInputRequiredError,
    SourceLimitError,
    SourceNotFoundError,
)
from app.features.maemusae.projects.models import ADMIN
from app.features.maemusae.versions import service as versions_service
from app.storage import PrivateStorage, get_private_storage
from app.storage.errors import StorageError

logger = logging.getLogger(__name__)

DOC_KIND_GROUP = "MMS_DOC_KIND"


def create_initial_documents(db: Session, project_id: int) -> None:
    """프로젝트를 만들 때 요구사항정의서 1행 (10/28 결정 4). 기능정의서·중간보고서는 그 기능을 만들 때 추가."""
    repository.add(db, Document(project_id=project_id, kind=REQUIREMENTS))


def _kind_labels(db: Session) -> dict[str, str]:
    # 꺼진 값도 이미 저장된 문서의 이름은 보여야 하므로 include_inactive
    return {code.code: code.label for code in list_codes(db, DOC_KIND_GROUP, include_inactive=True)}


def _document_read(db: Session, document: Document, source_count: int, labels: dict[str, str]) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        kind=document.kind,
        kind_label=labels.get(document.kind, document.kind),
        status=document.status,
        current_revision=document.current_revision,
        source_count=source_count,
        saved_at=document.saved_at,
        **versions_service.document_state(db, document),
        **confirm_service.warning_counts(db, document),
        confirmed_at=document.confirmed_at,
        confirmed_by_name=repository.get_user_name(db, document.confirmed_by),
        updated_at=document.updated_at,
    )


def _get_document(db: Session, access: ProjectAccess, document_id: int, *, for_update: bool = False) -> Document:
    document = repository.get_document(db, access.project.id, document_id, for_update=for_update)
    if document is None:
        raise DocumentNotFoundError()
    return document


def list_documents(db: Session, access: ProjectAccess) -> list[DocumentRead]:
    labels = _kind_labels(db)
    return [_document_read(db, d, n, labels) for d, n in repository.list_documents(db, access.project.id)]


def get_document(db: Session, access: ProjectAccess, document_id: int) -> DocumentRead:
    document = _get_document(db, access, document_id)
    return _document_read(db, document, repository.count_sources(db, document.id), _kind_labels(db))


# ---- 올린 파일 ----


def _source_read(source: SourceFile, uploader_name: str, actor_id: int) -> SourceRead:
    return SourceRead(
        id=source.id,
        source_type=source.source_type,
        filename=source.filename,
        content_type=source.content_type,
        size_bytes=source.size_bytes,
        page_count=source.page_count,
        uploaded_by_name=uploader_name,
        uploaded_by_me=source.uploaded_by == actor_id,
        created_at=source.created_at,
    )


def list_sources(db: Session, access: ProjectAccess, document_id: int) -> list[SourceRead]:
    document = _get_document(db, access, document_id)
    actor_id = access.principal.user_id
    return [_source_read(s, name, actor_id) for s, name in repository.list_sources(db, document.id)]


def add_source(
    db: Session,
    access: ProjectAccess,
    document_id: int,
    *,
    filename: str | None,
    data: bytes | None,
    text: str | None,
) -> SourceRead:
    """파일(filename+data) 또는 직접 쓴 글(text) 중 하나를 받아 쪽 단위로 나눠 저장합니다."""
    started = time.monotonic()
    has_text = bool(text and text.strip())
    if (data is None) == (not has_text):  # 둘 다 있거나 둘 다 없음
        raise SourceInputRequiredError()

    if data is not None:
        if len(data) > mms_settings.mms_source_max_bytes:
            raise FileTooLargeError(mms_settings.mms_source_max_bytes // (1024 * 1024))
        name = parsing.clean_filename(filename)
        converted = parsing.convert(data, name)  # 파싱은 잠그기 전에 (수 초 걸릴 수 있음)
        pages = converted.pages
        source = SourceFile(
            source_type=FILE,
            filename=name,
            content_type=converted.content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            storage_key=f"mms/projects/{access.project.id}/sources/{uuid.uuid4().hex}",
        )
    else:
        pages = [parsing.text_page(text)]
        source = SourceFile(source_type=TEXT)

    document = _get_document(db, access, document_id, for_update=True)
    if document.status in BUSY_STATUSES:
        raise DocumentBusyError()
    if repository.count_sources(db, document.id) >= mms_settings.mms_sources_per_document:
        raise SourceLimitError(mms_settings.mms_sources_per_document)
    if source.sha256 and repository.has_sha256(db, document.id, source.sha256):
        raise SourceDuplicateError()

    source.document_id = document.id
    source.page_count = len(pages)
    source.uploaded_by = access.principal.user_id

    storage = get_private_storage() if source.storage_key else None  # 설정이 비어 있으면 여기서 503
    if storage:
        storage.put(source.storage_key, data, source.content_type)
    try:
        repository.add(db, source)
        repository.add_all(
            db,
            [
                SourcePage(source_file_id=source.id, seq=i, page_no=p.page_no, location_label=p.location_label, text=p.text)
                for i, p in enumerate(pages, 1)
            ],
        )
        db.commit()
    except Exception as e:
        db.rollback()
        if storage:
            _delete_original(source.storage_key, source_id=None, storage=storage)
        if isinstance(e, IntegrityError):  # 같은 파일을 동시에 올림 (부분 유니크 인덱스)
            raise SourceDuplicateError() from e
        raise
    db.refresh(source)
    logger.info(
        "문서 파일 올림 project_id=%s document_id=%s source_id=%s type=%s bytes=%s pages=%s ms=%d actor_id=%s",
        access.project.id, document.id, source.id, source.source_type, source.size_bytes, source.page_count,
        (time.monotonic() - started) * 1000, access.principal.user_id,
    )
    return _source_read(source, repository.get_user_name(db, source.uploaded_by), access.principal.user_id)


def _get_source(db: Session, access: ProjectAccess, document_id: int, source_id: int) -> SourceFile:
    document = _get_document(db, access, document_id)
    source = repository.get_source(db, document.id, source_id)
    if source is None:
        raise SourceNotFoundError()
    return source


def list_pages(db: Session, access: ProjectAccess, document_id: int, source_id: int) -> list[SourcePageRead]:
    source = _get_source(db, access, document_id, source_id)
    return [SourcePageRead.model_validate(p, from_attributes=True) for p in repository.list_pages(db, source.id)]


def read_original(db: Session, access: ProjectAccess, document_id: int, source_id: int) -> tuple[SourceFile, bytes]:
    """원본 파일. 공개 주소가 없으므로 서버가 비공개 저장소에서 읽어 그대로 보냅니다. 직접 쓴 글은 원본이 없음(404)."""
    source = _get_source(db, access, document_id, source_id)
    if source.source_type != FILE:
        raise SourceNotFoundError()
    data = get_private_storage().get(source.storage_key)
    logger.info(
        "문서 원본 내려받기 project_id=%s source_id=%s actor_id=%s", access.project.id, source.id, access.principal.user_id
    )
    return source, data


def delete_source(db: Session, access: ProjectAccess, document_id: int, source_id: int) -> None:
    """올린 사람 또는 프로젝트 관리자. 분석·확정 중에는 409."""
    document = _get_document(db, access, document_id, for_update=True)
    source = repository.get_source(db, document.id, source_id)
    if source is None:
        raise SourceNotFoundError()
    if source.uploaded_by != access.principal.user_id and access.role != ADMIN:
        raise SourceDeleteForbiddenError()
    if document.status in BUSY_STATUSES:
        raise DocumentBusyError()
    key = source.storage_key
    repository.delete(db, source)
    db.commit()
    if key:
        _delete_original(key, source_id=source_id)
    logger.info(
        "문서 파일 삭제 project_id=%s document_id=%s source_id=%s actor_id=%s",
        access.project.id, document.id, source_id, access.principal.user_id,
    )


def _delete_original(key: str, *, source_id: int | None, storage: PrivateStorage | None = None) -> None:
    try:
        (storage or get_private_storage()).delete(key)
    except StorageError:
        # DB 에는 이미 없어서 아무도 받을 수 없습니다. 저장소에 남은 파일은 정리 명령(M4)이 다시 지웁니다
        logger.warning("문서 원본 삭제 실패 source_id=%s key=%s", source_id, key)

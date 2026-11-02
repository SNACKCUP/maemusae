"""버전 추가·버전 저장·버전 기록 (10/29 SoYoung 결정, 계획 17의 2-1). 권한 검사(보기)는 access.py 가 끝낸 뒤에 불립니다.

- 버전 추가: 누를 때마다 지금 후보·근거·입력 전체를 새 버전(v1, v2…)으로 남김
- 버전 저장: 이번 분석 이후 버전을 남겼으면(mms_documents.saved_at 있음) 그 마지막 버전을 덮어쓰고, 아니면 새 버전.
  다시 분석 전의 버전이 새 분석 내용으로 덮이지 않게 하려는 것 (다시 분석하면 runner 가 saved_at 을 비움)
- 다시 분석은 버전 번호를 건드리지 않음. 버전 번호는 이 두 버튼으로만 올라감
- 쓰기는 멤버만(보기 전용 MASTER 403), 분석·확정 중이면 409. 문서 행을 배타 잠금해 번호가 겹치지 않게 함

로그에는 id·버전 번호·후보 수만 남기고 내용은 남기지 않습니다.
"""

import logging
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.documents.models import Document
from app.features.maemusae.errors import NothingToVersionError, VersionNotFoundError
from app.features.maemusae.review.service import (
    TEXT_SOURCE_NAME,
    code_of,
    editable_document,
    get_document,
)
from app.features.maemusae.versions import repository
from app.features.maemusae.versions.models import SAVED, DocumentVersion
from app.features.maemusae.versions.schemas import (
    VersionDetail,
    VersionEvidence,
    VersionItem,
    VersionListItem,
    VersionNote,
    VersionSaved,
)

logger = logging.getLogger(__name__)

TITLE = "요구사항정의서"


def snapshot(db: Session, document_id: int) -> list[dict]:
    """지금 후보·근거·입력 전체 (JSON 으로 저장할 모양)"""
    sources: dict[int, list[VersionEvidence]] = defaultdict(list)
    for requirement_id, filename, label, end_label, quote, verified in repository.list_document_sources(db, document_id):
        sources[requirement_id].append(
            VersionEvidence(
                filename=filename or TEXT_SOURCE_NAME,
                location_label=label,
                end_location_label=end_label,
                quote=quote,
                verified=verified,
            )
        )
    notes: dict[int, list[VersionNote]] = defaultdict(list)
    for requirement_id, field, text, author, updated_at in repository.list_document_notes(db, document_id):
        notes[requirement_id].append(VersionNote(field=field, text=text, author_name=author, updated_at=updated_at))
    return [
        VersionItem(
            code=code_of(r.seq),
            name=r.name,
            kind=r.kind,
            priority=r.priority,
            category_major=r.category_major,
            category_middle=r.category_middle,
            category_minor=r.category_minor,
            description=r.description,
            ai_question=r.ai_question,
            ai_answer=r.ai_answer,
            is_included=r.is_included,
            is_manual=r.is_manual,
            kind_defaulted=r.kind_defaulted,
            priority_defaulted=r.priority_defaulted,
            sources=sources[r.id],
            notes=notes[r.id],
        ).model_dump(mode="json")
        for r in repository.list_live_requirements(db, document_id)
    ]


def _write(db: Session, access: ProjectAccess, document_id: int, *, overwrite: bool) -> VersionSaved:
    document = editable_document(db, access, document_id, exclusive=True)
    items = snapshot(db, document.id)
    if not items:
        raise NothingToVersionError()
    actor_id = access.principal.user_id
    # 후보 updated_at(DB now())과 같은 시계로 비교해야 '버전 남긴 뒤 또 고침'이 맞게 나옴
    now = db.scalar(select(func.now()))
    last = repository.get_last_saved(db, document.id) if overwrite and document.saved_at is not None else None
    if last is not None:
        last.items = items
        last.item_count = len(items)
        last.updated_by = actor_id
        last.updated_at = now
        version = last
    else:
        version = DocumentVersion(
            document_id=document.id,
            kind=SAVED,
            version_no=repository.last_version_no(db, document.id) + 1,
            title=TITLE,
            item_count=len(items),
            items=items,
            created_by=actor_id,
        )
        repository.add(db, version)
    document.saved_at = now
    document.saved_by = actor_id
    db.commit()
    logger.info(
        "요구사항 버전 %s document_id=%s version_id=%s version_no=%s items=%s actor_id=%s",
        "덮어씀" if last is not None else "추가", document.id, version.id, version.version_no, len(items), actor_id,
    )
    return VersionSaved(id=version.id, version_no=version.version_no, saved_at=now, overwritten=last is not None)


def add_version(db: Session, access: ProjectAccess, document_id: int) -> VersionSaved:
    return _write(db, access, document_id, overwrite=False)


def save_version(db: Session, access: ProjectAccess, document_id: int) -> VersionSaved:
    return _write(db, access, document_id, overwrite=True)


def _list_item(version: DocumentVersion, creator: str, updater: str | None) -> VersionListItem:
    return VersionListItem(
        id=version.id,
        kind=version.kind,
        version_no=version.version_no,
        revision=version.revision,
        item_count=version.item_count,
        created_by_name=creator,
        created_at=version.created_at,
        updated_by_name=updater,
        updated_at=version.updated_at,
    )


def list_versions(db: Session, access: ProjectAccess, document_id: int) -> list[VersionListItem]:
    document = get_document(db, access, document_id)
    return [_list_item(*row) for row in repository.list_versions(db, document.id)]


def get_version(db: Session, access: ProjectAccess, document_id: int, version_id: int) -> VersionDetail:
    document = get_document(db, access, document_id)
    row = repository.get_version(db, document.id, version_id)
    if row is None:
        raise VersionNotFoundError()
    version = row[0]
    return VersionDetail(**_list_item(*row).model_dump(), items=[VersionItem(**item) for item in version.items])


def document_state(db: Session, document: Document) -> dict:
    """문서 응답에 더하는 판단 값: 다시 분석 확인 창 문구와 '마지막 버전 v2 (16:32)' 표시용"""
    return {
        "last_version_no": repository.last_version_no(db, document.id) or None,
        "changed_since_save": document.saved_at is not None and repository.changed_since(db, document.id, document.saved_at),
        "manual_count": repository.manual_count(db, document.id),
    }

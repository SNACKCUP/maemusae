"""버전 기록 테이블 접근과 버전에 담을 내용 읽기. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.features.maemusae.analysis.models import Requirement, RequirementSource
from app.features.maemusae.documents.models import SourceFile, SourcePage
from app.features.maemusae.review.models import RequirementNote
from app.features.maemusae.versions.models import SAVED, DocumentVersion
from app.users.models import User


def add(db: Session, version: DocumentVersion) -> None:
    db.add(version)
    db.flush()


def last_version_no(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.max(DocumentVersion.version_no), 0)).where(
            DocumentVersion.document_id == document_id, DocumentVersion.kind == SAVED
        )
    )


def get_last_saved(db: Session, document_id: int) -> DocumentVersion | None:
    return db.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id, DocumentVersion.kind == SAVED)
        .order_by(DocumentVersion.version_no.desc())
        .limit(1)
    )


def list_versions(db: Session, document_id: int) -> list[tuple[DocumentVersion, str, str | None]]:
    """(버전, 만든 사람, 덮어쓴 사람) 최신순. items 는 읽지 않음"""
    creator, updater = aliased(User), aliased(User)
    rows = db.execute(
        select(DocumentVersion, creator.name, updater.name)
        .join(creator, creator.id == DocumentVersion.created_by)
        .outerjoin(updater, updater.id == DocumentVersion.updated_by)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.created_at.desc(), DocumentVersion.id.desc())
    )
    return [tuple(row) for row in rows]


def get_version(db: Session, document_id: int, version_id: int) -> tuple[DocumentVersion, str, str | None] | None:
    creator, updater = aliased(User), aliased(User)
    row = db.execute(
        select(DocumentVersion, creator.name, updater.name)
        .join(creator, creator.id == DocumentVersion.created_by)
        .outerjoin(updater, updater.id == DocumentVersion.updated_by)
        .where(DocumentVersion.document_id == document_id, DocumentVersion.id == version_id)
    ).first()
    return tuple(row) if row else None


# ---- 버전에 담을 내용 (후보 수가 많아도 쿼리 3번) ----


def _live(document_id: int):
    return (Requirement.document_id == document_id, Requirement.deleted_at.is_(None))


def list_live_requirements(db: Session, document_id: int) -> list[Requirement]:
    return list(db.scalars(select(Requirement).where(*_live(document_id)).order_by(Requirement.seq)))


def list_document_sources(db: Session, document_id: int) -> list[tuple[int, str | None, str, str | None, str, bool]]:
    """(후보 id, 파일 이름, 위치, 끝 위치, 문장, 확인됨) 후보·순서대로"""
    end_page = aliased(SourcePage)
    rows = db.execute(
        select(
            RequirementSource.requirement_id,
            SourceFile.filename,
            SourcePage.location_label,
            end_page.location_label,
            RequirementSource.quote,
            RequirementSource.verified,
        )
        .join(Requirement, Requirement.id == RequirementSource.requirement_id)
        .join(SourcePage, SourcePage.id == RequirementSource.source_page_id)
        .join(SourceFile, SourceFile.id == SourcePage.source_file_id)
        .outerjoin(end_page, end_page.id == RequirementSource.end_source_page_id)
        .where(*_live(document_id))
        .order_by(RequirementSource.requirement_id, RequirementSource.sort_order)
    )
    return [tuple(row) for row in rows]


def list_document_notes(db: Session, document_id: int) -> list[tuple[int, str, str, str, datetime]]:
    """(후보 id, 칸, 글, 작성자 이름, 고친 시각) 오래된 순"""
    rows = db.execute(
        select(
            RequirementNote.requirement_id, RequirementNote.field, RequirementNote.text, User.name,
            RequirementNote.updated_at,
        )
        .join(Requirement, Requirement.id == RequirementNote.requirement_id)
        .join(User, User.id == RequirementNote.author_id)
        .where(*_live(document_id))
        .order_by(RequirementNote.requirement_id, RequirementNote.updated_at, RequirementNote.id)
    )
    return [tuple(row) for row in rows]


# ---- 문서 응답의 판단 값 ----


def changed_since(db: Session, document_id: int, since: datetime) -> bool:
    """since 뒤에 후보(지운 표시 포함)나 입력이 바뀌었는지. 입력을 지우면 service 가 그 후보의 updated_at 을 올림"""
    requirement_changed = exists().where(Requirement.document_id == document_id, Requirement.updated_at > since)
    note_changed = (
        exists()
        .where(RequirementNote.requirement_id == Requirement.id, RequirementNote.updated_at > since)
        .where(Requirement.document_id == document_id)
    )
    return bool(db.scalar(select(or_(requirement_changed, note_changed))))


def manual_count(db: Session, document_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Requirement).where(*_live(document_id), Requirement.is_manual))

"""확정 관련 SQL. commit 은 service 가 합니다."""

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

from app.features.maemusae.analysis.models import Requirement
from app.features.maemusae.documents.models import Document
from app.features.maemusae.review.models import ANSWER, RequirementNote
from app.features.maemusae.versions.models import CONFIRMED, DocumentVersion
from app.users.models import User


def _included(document_id: int):
    return (Requirement.document_id == document_id, Requirement.deleted_at.is_(None), Requirement.is_included)


def last_revision(db: Session, document_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.max(DocumentVersion.revision), 0)).where(
            DocumentVersion.document_id == document_id, DocumentVersion.kind == CONFIRMED
        )
    )


def clear_defaulted(db: Session, document_id: int) -> None:
    """확정한 후보는 관리자가 값을 받아들인 것으로 보고 'AI 값 확인' 표시를 풂 (10/29 결정 B). version·updated_at 은 그대로
    (사람이 고친 것이 아니라서, 다시 열었을 때 '버전 남긴 뒤 또 고침'으로 잡히지 않게)"""
    db.execute(
        update(Requirement)
        .where(*_included(document_id), (Requirement.kind_defaulted | Requirement.priority_defaulted))
        .values(kind_defaulted=False, priority_defaulted=False, updated_at=Requirement.updated_at)
        .execution_options(synchronize_session=False)
    )


def warning_counts(db: Session, document_id: int) -> tuple[int, int]:
    """체크된 후보 중 (답이 없는 AI 질문 수, AI 값 확인 표시 수). 확정 창 경고용"""
    answered = exists().where(RequirementNote.requirement_id == Requirement.id, RequirementNote.field == ANSWER)
    open_question = Requirement.ai_question.is_not(None) & ~answered
    defaulted = Requirement.kind_defaulted | Requirement.priority_defaulted
    row = db.execute(
        select(
            func.count().filter(open_question),
            func.count().filter(defaulted),
        ).where(*_included(document_id))
    ).one()
    return row[0], row[1]


def list_confirmed(db: Session, project_id: int) -> list[tuple[DocumentVersion, str, str]]:
    """(확정 기록, 문서 종류, 확정한 사람) 최신순. items 는 읽지 않음"""
    rows = db.execute(
        select(DocumentVersion, Document.kind, User.name)
        .join(Document, Document.id == DocumentVersion.document_id)
        .join(User, User.id == DocumentVersion.created_by)
        .where(Document.project_id == project_id, DocumentVersion.kind == CONFIRMED)
        .order_by(DocumentVersion.created_at.desc(), DocumentVersion.id.desc())
    )
    return [tuple(row) for row in rows]


def get_confirmed(db: Session, document_id: int, version_id: int) -> tuple[DocumentVersion, str] | None:
    row = db.execute(
        select(DocumentVersion, User.name)
        .join(User, User.id == DocumentVersion.created_by)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.id == version_id,
            DocumentVersion.kind == CONFIRMED,
        )
    ).first()
    return tuple(row) if row else None

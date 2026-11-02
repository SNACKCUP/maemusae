"""문서·올린 파일·쪽 본문 테이블 접근. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.users.models import User


def list_documents(db: Session, project_id: int) -> list[tuple[Document, int]]:
    """프로젝트의 문서와 올린 파일 수"""
    count = (
        select(func.count(SourceFile.id))
        .where(SourceFile.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    rows = db.execute(select(Document, count).where(Document.project_id == project_id).order_by(Document.id))
    return [(document, n) for document, n in rows]


def get_document(db: Session, project_id: int, document_id: int, *, for_update: bool = False) -> Document | None:
    """for_update=True 면 행을 잠가, 같은 문서에 동시에 올려도 파일 수·중복 검사가 어긋나지 않게 합니다."""
    stmt = select(Document).where(Document.project_id == project_id, Document.id == document_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def count_sources(db: Session, document_id: int) -> int:
    return db.scalar(select(func.count(SourceFile.id)).where(SourceFile.document_id == document_id))


def has_sha256(db: Session, document_id: int, sha256: str) -> bool:
    return db.scalar(
        select(SourceFile.id).where(SourceFile.document_id == document_id, SourceFile.sha256 == sha256)
    ) is not None


def list_sources(db: Session, document_id: int) -> list[tuple[SourceFile, str]]:
    """올린 파일과 올린 사람 이름. 올린 순"""
    rows = db.execute(
        select(SourceFile, User.name)
        .join(User, User.id == SourceFile.uploaded_by)
        .where(SourceFile.document_id == document_id)
        .order_by(SourceFile.created_at, SourceFile.id)
    )
    return [(source, name) for source, name in rows]


def get_source(db: Session, document_id: int, source_id: int) -> SourceFile | None:
    return db.scalar(select(SourceFile).where(SourceFile.document_id == document_id, SourceFile.id == source_id))


def list_pages(db: Session, source_id: int) -> list[SourcePage]:
    return list(db.scalars(select(SourcePage).where(SourcePage.source_file_id == source_id).order_by(SourcePage.seq)))


def get_user_name(db: Session, user_id: int | None) -> str | None:
    return db.scalar(select(User.name).where(User.id == user_id)) if user_id else None


def add(db: Session, row: Document | SourceFile | SourcePage) -> None:
    db.add(row)
    db.flush()


def add_all(db: Session, rows: list[SourcePage]) -> None:
    db.add_all(rows)
    db.flush()


def delete(db: Session, row: SourceFile) -> None:
    db.delete(row)  # 쪽 본문은 FK ON DELETE CASCADE 로 같이 지워짐
    db.flush()

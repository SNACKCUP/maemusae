"""보관 기간 정리용 조회·삭제. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.features.maemusae.documents.models import Document, SourceFile
from app.features.maemusae.projects.models import Project


def expired_project_ids(db: Session, cutoff: datetime) -> list[int]:
    """cutoff 이전에 삭제 표시한 프로젝트 id (오래된 것부터)"""
    stmt = (
        select(Project.id)
        .where(Project.deleted_at.is_not(None), Project.deleted_at < cutoff)
        .order_by(Project.deleted_at, Project.id)
    )
    return list(db.scalars(stmt))


def storage_keys_of_project(db: Session, project_id: int) -> list[str]:
    """프로젝트의 원본 파일 key (직접 쓴 글은 원본이 없어 빠짐)"""
    stmt = (
        select(SourceFile.storage_key)
        .join(Document, Document.id == SourceFile.document_id)
        .where(Document.project_id == project_id, SourceFile.storage_key.is_not(None))
        .order_by(SourceFile.id)
    )
    return list(db.scalars(stmt))


def delete_project(db: Session, project_id: int) -> None:
    """프로젝트 행 삭제. 나머지 매무새 행은 외래 키 ON DELETE CASCADE 로 함께 지워집니다."""
    db.execute(delete(Project).where(Project.id == project_id))

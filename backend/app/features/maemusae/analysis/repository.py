"""분석 요청·요구사항 후보·근거 테이블 접근. SQL 은 이 파일에만 둡니다. commit 은 service·runner 가 합니다."""


from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.features.maemusae.analysis.models import (
    RUNNING,
    AnalysisRun,
    Requirement,
    RequirementSource,
)
from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.features.maemusae.review.models import RequirementNote


def lock_document(db: Session, document_id: int) -> Document | None:
    return db.scalar(select(Document).where(Document.id == document_id).with_for_update())


def get_run(db: Session, run_id: int) -> AnalysisRun | None:
    return db.get(AnalysisRun, run_id, populate_existing=True)


def get_running_run(db: Session, document_id: int) -> AnalysisRun | None:
    return db.scalar(select(AnalysisRun).where(AnalysisRun.document_id == document_id, AnalysisRun.status == RUNNING))


def get_latest_run(db: Session, document_id: int) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun).where(AnalysisRun.document_id == document_id).order_by(AnalysisRun.id.desc()).limit(1)
    )


def list_document_pages(
    db: Session, document_id: int, *, only_new: bool = False
) -> list[tuple[SourcePage, SourceFile]]:
    """문서에 올린 모든 쪽. 파일은 올린 순, 파일 안은 seq 순 (묶음 나누기가 이 순서를 그대로 씀).
    only_new 면 아직 분석에 쓰지 않은 파일(analysis_run_id 없음)만 (다시 분류)"""
    stmt = (
        select(SourcePage, SourceFile)
        .join(SourceFile, SourceFile.id == SourcePage.source_file_id)
        .where(SourceFile.document_id == document_id)
        .order_by(SourceFile.created_at, SourceFile.id, SourcePage.seq)
    )
    if only_new:
        stmt = stmt.where(SourceFile.analysis_run_id.is_(None))
    return [(page, source) for page, source in db.execute(stmt)]


def _live(document_id: int):
    return (Requirement.document_id == document_id, Requirement.deleted_at.is_(None))


def has_live_requirements(db: Session, document_id: int) -> bool:
    return db.scalar(select(Requirement.id).where(*_live(document_id)).limit(1)) is not None


def max_seq(db: Session, document_id: int) -> int:
    """지운 후보까지 포함한 마지막 번호 (번호를 다시 쓰지 않으려고)"""
    return db.scalar(select(func.coalesce(func.max(Requirement.seq), 0)).where(Requirement.document_id == document_id))


def delete_requirements(db: Session, document_id: int) -> int:
    """다시 분석할 때 문서의 후보를 모두 지움 (AI·직접 추가·지운 표시 행 모두). 근거·입력은 FK CASCADE 로 같이 지워짐.
    남겨야 할 내용은 사람이 버전 추가·저장으로 mms_document_versions 에 남겼습니다 (10/29 결정)"""
    result = db.execute(
        delete(Requirement).where(Requirement.document_id == document_id).execution_options(synchronize_session=False)
    )
    return result.rowcount


def mark_sources_analyzed(db: Session, document_id: int, run_id: int, *, source_ids: list[int] | None = None) -> None:
    """분석에 쓴 파일 표시. source_ids 를 주면 그 파일만 (다시 분류가 읽은 새 파일)"""
    stmt = update(SourceFile).where(SourceFile.document_id == document_id)
    if source_ids is not None:
        stmt = stmt.where(SourceFile.id.in_(source_ids))
    db.execute(stmt.values(analysis_run_id=run_id).execution_options(synchronize_session=False))


# ---- 다시 분류 (M3-3) ----


def list_pending_notes(db: Session, document_id: int) -> list[tuple[RequirementNote, Requirement]]:
    """아직 다시 분류에 반영 안 된 입력과 그 후보. 후보 번호 순, 후보 안은 남긴 순. 작성자 이름은 읽지 않음 (AI 에 안 보냄)"""
    rows = db.execute(
        select(RequirementNote, Requirement)
        .join(Requirement, Requirement.id == RequirementNote.requirement_id)
        .where(*_live(document_id), RequirementNote.applied_run_id.is_(None))
        .order_by(Requirement.seq, RequirementNote.created_at, RequirementNote.id)
    )
    return [(note, requirement) for note, requirement in rows]


def has_pending_notes(db: Session, document_id: int) -> bool:
    stmt = (
        select(RequirementNote.id)
        .join(Requirement, Requirement.id == RequirementNote.requirement_id)
        .where(*_live(document_id), RequirementNote.applied_run_id.is_(None))
        .limit(1)
    )
    return db.scalar(stmt) is not None


def has_new_sources(db: Session, document_id: int) -> bool:
    stmt = select(SourceFile.id).where(SourceFile.document_id == document_id, SourceFile.analysis_run_id.is_(None))
    return db.scalar(stmt.limit(1)) is not None


def list_live_requirements(db: Session, document_id: int) -> list[Requirement]:
    return list(db.scalars(select(Requirement).where(*_live(document_id)).order_by(Requirement.seq)))


def list_category_paths(db: Session, document_id: int) -> list[tuple[str | None, str | None, str | None]]:
    """이 문서 후보가 쓰는 (대, 중, 소)분류. 번호 순으로 처음 나온 순서 (다시 분류 때 AI 에 같은 이름을 쓰게 함)"""
    rows = db.execute(
        select(Requirement.category_major, Requirement.category_middle, Requirement.category_minor)
        .where(*_live(document_id), Requirement.category_major.is_not(None))
        .order_by(Requirement.seq)
    )
    return list(dict.fromkeys(tuple(row) for row in rows))


def lock_requirements(db: Session, document_id: int, ids: list[int]) -> dict[int, Requirement]:
    """id 순으로 잠금 (사람의 일괄 수정과 같은 순서라 교착 없음)"""
    rows = db.scalars(
        select(Requirement)
        .where(Requirement.document_id == document_id, Requirement.id.in_(ids))
        .order_by(Requirement.id)
        .with_for_update()
        .execution_options(populate_existing=True)  # 분석 동안 사람이 고친 version 을 다시 읽음
    )
    return {r.id: r for r in rows}


def lock_notes(db: Session, ids: list[int]) -> list[RequirementNote]:
    stmt = (
        select(RequirementNote)
        .where(RequirementNote.id.in_(ids))
        .order_by(RequirementNote.id)
        .with_for_update()
        .execution_options(populate_existing=True)  # 분석 동안 고친 입력을 다시 읽음
    )
    return list(db.scalars(stmt))


def max_sort_orders(db: Session, requirement_ids: list[int]) -> dict[int, int]:
    rows = db.execute(
        select(RequirementSource.requirement_id, func.max(RequirementSource.sort_order))
        .where(RequirementSource.requirement_id.in_(requirement_ids))
        .group_by(RequirementSource.requirement_id)
    )
    return {rid: n for rid, n in rows}


def add(db: Session, row: AnalysisRun | Requirement) -> None:
    db.add(row)
    db.flush()


def add_all(db: Session, rows: list[RequirementSource]) -> None:
    db.add_all(rows)
    db.flush()

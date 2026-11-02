"""요구사항 후보 검토·입력 테이블 접근. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from dataclasses import dataclass

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.features.maemusae.analysis.models import Requirement, RequirementSource
from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.features.maemusae.review.models import ANSWER, RequirementNote
from app.users.models import User


@dataclass(frozen=True)
class RequirementFilter:
    kind: str | None = None
    priority: str | None = None
    category_major: str | None = None
    included: bool | None = None
    needs_check: bool = False  # 확인 필요만: 답 없는 AI 질문, 기본값 표시, 위치 확인 필요 근거
    seq: int | None = None  # REQ-012 로 찾기
    name: str | None = None  # 이름에 들어간 글자로 찾기
    ids: tuple[int, ...] | None = None


def lock_document(db: Session, project_id: int, document_id: int, *, exclusive: bool) -> Document | None:
    """고치는 동안 분석 시작·확정이 끼어들지 않게 문서 행을 잠금. 후보만 고칠 때는 공유 잠금(여러 명이 동시에 고칠 수 있음)"""
    stmt = select(Document).where(Document.project_id == project_id, Document.id == document_id)
    return db.scalar(stmt.with_for_update(read=not exclusive))


def _live(document_id: int):
    return (Requirement.document_id == document_id, Requirement.deleted_at.is_(None))


def _flags():
    answered = exists().where(RequirementNote.requirement_id == Requirement.id, RequirementNote.field == ANSWER)
    unverified = exists().where(RequirementSource.requirement_id == Requirement.id, RequirementSource.verified.is_(False))
    has_source = exists().where(RequirementSource.requirement_id == Requirement.id)
    needs_answer = and_(Requirement.ai_question.is_not(None), ~answered)
    return needs_answer, and_(has_source, ~unverified), unverified


def list_requirements(
    db: Session, document_id: int, f: RequirementFilter, *, after_seq: int | None = None, limit: int | None = None
) -> list[tuple[Requirement, bool, bool]]:
    """(후보, needs_answer, verified_all) 목록. 번호 순, after_seq 다음부터"""
    needs_answer, verified_all, unverified = _flags()
    stmt = select(Requirement, needs_answer.label("needs_answer"), verified_all.label("verified_all")).where(
        *_live(document_id)
    )
    if f.kind:
        stmt = stmt.where(Requirement.kind == f.kind)
    if f.priority:
        stmt = stmt.where(Requirement.priority == f.priority)
    if f.category_major:
        stmt = stmt.where(Requirement.category_major == f.category_major)
    if f.included is not None:
        stmt = stmt.where(Requirement.is_included.is_(f.included))
    if f.needs_check:
        stmt = stmt.where(or_(needs_answer, Requirement.kind_defaulted, Requirement.priority_defaulted, unverified))
    if f.seq is not None:
        stmt = stmt.where(Requirement.seq == f.seq)
    if f.name:
        stmt = stmt.where(Requirement.name.ilike(f"%{_escape(f.name)}%", escape="\\"))
    if f.ids is not None:
        stmt = stmt.where(Requirement.id.in_(f.ids))
    if after_seq is not None:
        stmt = stmt.where(Requirement.seq > after_seq)
    stmt = stmt.order_by(Requirement.seq)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [(r, bool(a), bool(v)) for r, a, v in db.execute(stmt)]


def list_category_paths(db: Session, document_id: int) -> list[tuple[str, str | None, str | None, int]]:
    """(대, 중, 소, 후보 수) 가나다 순. 분류 없는 후보는 빼고 셈"""
    rows = db.execute(
        select(Requirement.category_major, Requirement.category_middle, Requirement.category_minor, func.count())
        .where(*_live(document_id), Requirement.category_major.is_not(None))
        .group_by(Requirement.category_major, Requirement.category_middle, Requirement.category_minor)
        .order_by(
            Requirement.category_major,
            Requirement.category_middle.nulls_first(),
            Requirement.category_minor.nulls_first(),
        )
    )
    return [tuple(row) for row in rows]


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_requirement(db: Session, document_id: int, requirement_id: int, *, for_update: bool = False) -> Requirement | None:
    stmt = select(Requirement).where(*_live(document_id), Requirement.id == requirement_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def lock_requirements(db: Session, document_id: int, ids: list[int]) -> list[Requirement]:
    """일괄 수정. id 순으로 잠가 서로 기다리다 멈추는(교착) 일을 막음"""
    stmt = select(Requirement).where(*_live(document_id), Requirement.id.in_(ids)).order_by(Requirement.id)
    return list(db.scalars(stmt.with_for_update()))


def list_sources(db: Session, requirement_id: int) -> list[tuple[RequirementSource, SourcePage, SourceFile, str | None]]:
    """근거와 그 쪽·파일, 끝 쪽 이름"""
    end_page = aliased(SourcePage)
    rows = db.execute(
        select(RequirementSource, SourcePage, SourceFile, end_page.location_label)
        .join(SourcePage, SourcePage.id == RequirementSource.source_page_id)
        .join(SourceFile, SourceFile.id == SourcePage.source_file_id)
        .outerjoin(end_page, end_page.id == RequirementSource.end_source_page_id)
        .where(RequirementSource.requirement_id == requirement_id)
        .order_by(RequirementSource.sort_order)
    )
    return [tuple(row) for row in rows]


def list_notes(
    db: Session,
    document_id: int,
    *,
    requirement_id: int | None = None,
    author_id: int | None = None,
    seq: int | None = None,
    name: str | None = None,
    newest_first: bool = True,
    limit: int | None = None,
) -> list[tuple[RequirementNote, Requirement, str]]:
    """(입력, 후보, 작성자 이름). 지운 후보에 남은 입력은 빼고 보여 줌"""
    stmt = (
        select(RequirementNote, Requirement, User.name)
        .join(Requirement, Requirement.id == RequirementNote.requirement_id)
        .join(User, User.id == RequirementNote.author_id)
        .where(*_live(document_id))
    )
    if requirement_id is not None:
        stmt = stmt.where(RequirementNote.requirement_id == requirement_id)
    if author_id is not None:
        stmt = stmt.where(RequirementNote.author_id == author_id)
    if seq is not None:
        stmt = stmt.where(Requirement.seq == seq)
    if name:
        stmt = stmt.where(Requirement.name.ilike(f"%{_escape(name)}%", escape="\\"))
    order = RequirementNote.updated_at.desc() if newest_first else RequirementNote.updated_at.asc()
    stmt = stmt.order_by(order, RequirementNote.id.desc() if newest_first else RequirementNote.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [(note, req, author) for note, req, author in db.execute(stmt)]


def get_my_note(db: Session, requirement_id: int, field: str, author_id: int) -> RequirementNote | None:
    return db.scalar(
        select(RequirementNote)
        .where(
            RequirementNote.requirement_id == requirement_id,
            RequirementNote.field == field,
            RequirementNote.author_id == author_id,
        )
        .with_for_update()
    )


def get_user_name(db: Session, user_id: int) -> str:
    return db.scalar(select(User.name).where(User.id == user_id))


def add(db: Session, row: Requirement | RequirementNote) -> None:
    db.add(row)
    db.flush()


def delete(db: Session, row: RequirementNote) -> None:
    db.delete(row)
    db.flush()

"""AI 분석 시작·진행률. 권한 검사(멤버·보기)는 access.py 가 끝낸 뒤에 불립니다. 분석 자체는 runner.py 가 뒤에서 돌립니다.

시작 순서: 문서 잠금 → 멈춘 분석 정리 → 상태 확인 → 올린 문서·묶음 수 확인 → 분석 요청 RUNNING + 문서 ANALYZING
→ commit 뒤 202. 라우터가 BackgroundTasks 에 runner.run_analysis(run_id) 를 넣습니다.

다시 분류(M3-3, start_refine): 반영 안 된 입력이 달린 후보와 아직 분석에 안 쓴 새 파일만 AI 에 보냅니다 (refine_plan).
후보 번호·id 는 그대로, 버전 번호·saved_at 도 건드리지 않습니다.

분석 방식은 크기로 고릅니다 (10/29 확정, choose_plan): 전체가 묶음 하나면 AI 1번(합치기 생략), 여럿이면 묶음마다 뽑고 합치기,
묶음 수가 상한을 넘으면 시작 전에 422. 엑셀 표 방식(M4 뒤, 계획 17의 6장)은 이 함수에 갈림길만 더하면 됩니다.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.maemusae.access import ProjectAccess
from app.features.maemusae.analysis import repository
from app.features.maemusae.analysis.batching import Batch, PageRef, make_batches
from app.features.maemusae.analysis.models import (
    ANALYZE,
    FAILED,
    REFINE,
    RUNNING,
    AnalysisRun,
)
from app.features.maemusae.analysis.schemas import (
    AnalysisRunRead,
    AnalysisStarted,
    AnalyzeRequest,
    RefineRequest,
)
from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents import repository as documents_repository
from app.features.maemusae.documents.models import (
    ANALYZING,
    BUSY_STATUSES,
    CONFIRMED,
    READY,
    Document,
)
from app.features.maemusae.documents.models import FAILED as DOCUMENT_FAILED
from app.features.maemusae.errors import (
    AnalysisNoSourcesError,
    AnalysisRestartRequiredError,
    DocumentBusyError,
    DocumentConfirmedError,
    DocumentNotFoundError,
    DocumentTooLargeToAnalyzeError,
    ProjectMemberRequiredError,
    RefineNeedsRequirementsError,
    RefineNothingNewError,
)

logger = logging.getLogger(__name__)

INTERRUPTED = "ANALYSIS_INTERRUPTED"
TEXT_SOURCE_NAME = "직접 입력"


@dataclass(frozen=True)
class AnalysisPlan:
    batches: list[Batch]
    by_tag: dict[str, PageRef]
    dedupe: bool  # 묶음이 여럿일 때만 합치기

    @property
    def total_steps(self) -> int:
        return len(self.batches) + (1 if self.dedupe else 0)


def _page_ref(page, source) -> PageRef:
    return PageRef(
        id=page.id,
        source_file_id=source.id,
        seq=page.seq,
        filename=source.filename or TEXT_SOURCE_NAME,
        location_label=page.location_label,
        text=page.text,
    )


def load_pages(db: Session, document_id: int) -> list[PageRef]:
    return [_page_ref(page, source) for page, source in repository.list_document_pages(db, document_id)]


def choose_plan(pages: list[PageRef]) -> AnalysisPlan:
    """크기로 분석 방식 고르기. 너무 크면 422"""
    batches, by_tag = make_batches(
        pages, limit=mms_settings.mms_batch_chars, overlap=mms_settings.mms_batch_overlap_chars
    )
    if len(batches) > mms_settings.mms_analyze_max_batches:
        raise DocumentTooLargeToAnalyzeError()
    return AnalysisPlan(batches, by_tag, dedupe=len(batches) > 1)


@dataclass(frozen=True)
class RefineTarget:
    """다시 분류에 보낼 후보 하나와 그 입력. version·입력 시각은 저장할 때 그사이 사람이 고쳤는지 보려고 둠"""

    tag: str  # R1, R2… (AI 가 답에 쓰는 번호표)
    requirement_id: int
    version: int
    text: str
    notes: tuple[tuple[int, datetime], ...]  # (입력 id, 고친 시각)


@dataclass(frozen=True)
class RefinePlan:
    chunks: list[list[RefineTarget]]  # AI 호출 한 번에 보낼 후보 묶음
    extract: AnalysisPlan | None  # 새 파일 (없으면 None)
    new_source_ids: list[int]

    @property
    def total_steps(self) -> int:
        batches = len(self.extract.batches) if self.extract else 0
        return len(self.chunks) + batches + (1 if batches else 0)  # 새 파일이 있으면 기존 후보와 맞춰 보기 1번


NOTE_LABELS = {"DESCRIPTION": "설명 의견", "ANSWER": "질문 답"}


def _target_text(tag: str, requirement, notes: list) -> str:
    code = f"REQ-{requirement.seq:03d}"
    lines = [f"[{tag} · {code} · {requirement.name} · 구분 {requirement.kind} · 우선순위 {requirement.priority}]"]
    path = " > ".join(p for p in (requirement.category_major, requirement.category_middle, requirement.category_minor) if p)
    lines.append(f"분류: {path or '(없음)'}")
    lines.append(f"설명: {requirement.description or '(없음)'}")
    if requirement.ai_question:
        lines.append(f"AI 질문: {requirement.ai_question}")
    # 작성자 이름은 보내지 않고 번호로만 구분 (개인정보를 AI 에 넘기지 않음, 10/28 결정 5)
    lines += [f"입력 {i} ({NOTE_LABELS.get(n.field, n.field)}): {n.text}" for i, n in enumerate(notes, 1)]
    return "\n".join(lines)


def build_targets(db: Session, document_id: int) -> list[RefineTarget]:
    grouped: dict[int, tuple] = {}
    for note, requirement in repository.list_pending_notes(db, document_id):
        grouped.setdefault(requirement.id, (requirement, []))[1].append(note)
    return [
        RefineTarget(
            tag=f"R{i}",
            requirement_id=requirement.id,
            version=requirement.version,
            text=_target_text(f"R{i}", requirement, notes),
            notes=tuple((n.id, n.updated_at) for n in notes),
        )
        for i, (requirement, notes) in enumerate(grouped.values(), 1)
    ]


def _chunk(targets: list[RefineTarget], limit: int) -> list[list[RefineTarget]]:
    chunks: list[list[RefineTarget]] = []
    size = 0
    for target in targets:
        if chunks and size + len(target.text) <= limit:
            chunks[-1].append(target)
            size += len(target.text)
        else:
            chunks.append([target])
            size = len(target.text)
    return chunks


def refine_plan(db: Session, document_id: int) -> RefinePlan:
    """다시 분류 계획. 너무 크면 422 (새 파일 묶음 + 입력 묶음이 상한을 넘을 때)"""
    chunks = _chunk(build_targets(db, document_id), mms_settings.mms_batch_chars)
    rows = repository.list_document_pages(db, document_id, only_new=True)
    pages = [_page_ref(page, source) for page, source in rows]
    extract = None
    if pages:
        batches, by_tag = make_batches(
            pages, limit=mms_settings.mms_batch_chars, overlap=mms_settings.mms_batch_overlap_chars
        )
        extract = AnalysisPlan(batches, by_tag, dedupe=len(batches) > 1)
    plan = RefinePlan(chunks, extract, sorted({source.id for _, source in rows}))
    if plan.total_steps > mms_settings.mms_analyze_max_batches:
        raise DocumentTooLargeToAnalyzeError()
    return plan


def end_failed(db: Session, run: AnalysisRun, document: Document, code: str) -> None:
    """분석 실패 처리 (commit 은 부른 쪽). 후보가 이미 있으면(다시 분석하다 실패) 문서는 READY 로 두어 기존 후보를 계속 쓰게 함"""
    run.status = FAILED
    run.error_code = code
    run.finished_at = datetime.now(UTC)
    document.status = READY if repository.has_live_requirements(db, document.id) else DOCUMENT_FAILED


def expire_stale(db: Session, document_id: int) -> None:
    """RUNNING 인데 MMS_ANALYZE_STALE_MINUTES 동안 진행이 없으면 실패로 정리 (서버 재시작 등으로 멈춘 분석)"""
    run = repository.get_running_run(db, document_id)
    limit = datetime.now(UTC) - timedelta(minutes=mms_settings.mms_analyze_stale_minutes)
    if run is None or run.updated_at > limit:
        return
    document = repository.lock_document(db, document_id)
    run = repository.get_run(db, run.id)  # 잠근 뒤 다시 읽기 (그사이 끝났을 수 있음)
    if run.status != RUNNING or run.updated_at > limit:
        return
    end_failed(db, run, document, INTERRUPTED)
    db.commit()
    logger.warning("AI 분석 멈춤 정리 run_id=%s document_id=%s done=%s/%s", run.id, document_id, run.done_steps, run.total_steps)


def start_analysis(db: Session, access: ProjectAccess, document_id: int, body: AnalyzeRequest) -> AnalysisStarted:
    document = _start_checks(db, access, document_id)
    if not body.restart and repository.has_live_requirements(db, document.id):
        raise AnalysisRestartRequiredError()
    pages = load_pages(db, document.id)
    if not pages:
        raise AnalysisNoSourcesError()
    plan = choose_plan(pages)

    run = AnalysisRun(
        document_id=document.id,
        run_type=ANALYZE,
        prompt=(body.prompt or "").strip() or None,
        requested_by=access.principal.user_id,
        total_steps=plan.total_steps,
        done_steps=0,
    )
    _create_run(db, document, run)
    logger.info(
        "AI 분석 시작 project_id=%s document_id=%s run_id=%s batches=%s restart=%s actor_id=%s",
        access.project.id, document.id, run.id, len(plan.batches), body.restart, access.principal.user_id,
    )
    return AnalysisStarted(run_id=run.id)


def _start_checks(db: Session, access: ProjectAccess, document_id: int) -> Document:
    if access.member is None:  # 보기 전용 MASTER
        raise ProjectMemberRequiredError()
    if documents_repository.get_document(db, access.project.id, document_id) is None:
        raise DocumentNotFoundError()
    expire_stale(db, document_id)
    document = documents_repository.get_document(db, access.project.id, document_id, for_update=True)
    if document.status == CONFIRMED:
        raise DocumentConfirmedError()
    if document.status in BUSY_STATUSES:
        raise DocumentBusyError()
    return document


def _create_run(db: Session, document: Document, run: AnalysisRun) -> None:
    document.status = ANALYZING
    try:
        repository.add(db, run)
        db.commit()
    except IntegrityError as e:  # 같은 문서에 동시에 눌러 RUNNING 이 둘 (부분 유니크 인덱스)
        db.rollback()
        raise DocumentBusyError() from e


def start_refine(db: Session, access: ProjectAccess, document_id: int, body: RefineRequest) -> AnalysisStarted:
    """다시 분류 시작. 후보가 있어야 하고, 반영 안 된 입력이나 새 파일이 있어야 함"""
    document = _start_checks(db, access, document_id)
    if not repository.has_live_requirements(db, document.id):
        raise RefineNeedsRequirementsError()
    if not repository.has_pending_notes(db, document.id) and not repository.has_new_sources(db, document.id):
        raise RefineNothingNewError()
    plan = refine_plan(db, document.id)
    run = AnalysisRun(
        document_id=document.id,
        run_type=REFINE,
        prompt=(body.prompt or "").strip() or None,
        requested_by=access.principal.user_id,
        total_steps=plan.total_steps,
        done_steps=0,
    )
    _create_run(db, document, run)
    logger.info(
        "AI 다시 분류 시작 project_id=%s document_id=%s run_id=%s targets=%s new_sources=%s actor_id=%s",
        access.project.id, document.id, run.id, sum(len(c) for c in plan.chunks), len(plan.new_source_ids),
        access.principal.user_id,
    )
    return AnalysisStarted(run_id=run.id)


def get_latest_run(db: Session, access: ProjectAccess, document_id: int) -> AnalysisRunRead | None:
    if documents_repository.get_document(db, access.project.id, document_id) is None:
        raise DocumentNotFoundError()
    expire_stale(db, document_id)
    run = repository.get_latest_run(db, document_id)
    if run is None:
        return None
    return AnalysisRunRead(
        run_id=run.id,
        run_type=run.run_type,
        status=run.status,
        done_steps=run.done_steps,
        total_steps=run.total_steps,
        error_code=run.error_code,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )

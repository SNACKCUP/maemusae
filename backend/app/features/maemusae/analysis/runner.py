"""뒤에서 돌리는 AI 분석 (BackgroundTasks). 요청과 다른 DB 세션을 직접 열고, 오류를 밖으로 던지지 않습니다.

1. 묶음마다 prompts/extract.md 로 후보를 뽑고 done_steps +1 (commit 해서 화면 진행률·멈춤 판단에 씀)
2. 묶음이 여럿이면 prompts/dedupe.md 로 같은 후보를 묶어 하나로 (근거는 모두 남김)
   MMS_ANALYZE_EXPAND 가 켜져 있으면 prompts/expand.md 로 후보 EXPAND_CHUNK 개씩 숨은 요구사항(예: 로그인 → 리프레시 토큰)을 찾아
   출발한 후보 바로 뒤에 넣음. 근거는 출발한 후보의 근거를 그대로 씀 (AI 가 근거를 지어내지 않게)
   MMS_ANALYZE_DETAIL 이 켜져 있으면 prompts/detail.md 로 후보 DETAIL_CHUNK 개씩 자세한 명세를 씀.
   뽑기는 짧게 하고 명세는 따로 쓰는 이유: 한 번에 쓰는 답이 길면 큰 묶음에서 시간 초과가 남 (11/3 과업지시서 시험)
   여러 AI 호출은 MMS_ANALYZE_CONCURRENCY 개까지 동시에, 실패한 호출만 MMS_BATCH_RETRIES 번 다시 보냄
3. 근거 문장을 서버가 쪽 본문에서 찾아 verified·끝 쪽을 정함. 없는 쪽 번호를 댄 근거는 버림
4. 문서를 잠그고, 분석 요청이 아직 RUNNING 일 때만 한 트랜잭션으로 저장 (멈춤 정리와 겹치면 저장하지 않음).
   저장할 때 이전 후보·직접 추가·입력을 모두 지우고 REQ-001 부터 다시 매깁니다. 버전 번호는 건드리지 않고
   "이번 분석 이후 버전을 남겼는지" 표시(saved_at)만 비웁니다 (10/29 결정, 계획 17의 2-1)
다시 분류(run_refine, M3-3)는 아래 "다시 분류" 절에 있습니다.
어느 단계든 실패하면 반쯤 만든 결과는 저장하지 않고 run FAILED + 오류 코드 (킷 LLM 오류 코드 그대로).

로그에는 id·묶음 수·후보 수·걸린 시간·오류 코드만. 문서 본문·후보 내용·지시문은 남기지 않습니다.
"""

import contextvars
import logging
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from sqlalchemy.orm import Session

from app.codes import list_codes
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.features.maemusae.analysis import repository
from app.features.maemusae.analysis.batching import PageRef, locate, normalize, tag_of
from app.features.maemusae.analysis.categories import CategoryBook, CategoryPath
from app.features.maemusae.analysis.models import (
    RUNNING,
    SUCCEEDED,
    AnalysisRun,
    Requirement,
    RequirementSource,
)
from app.features.maemusae.analysis.schemas import (
    DedupeResult,
    DetailResult,
    ExpandResult,
    ExtractedRequirement,
    ExtractResult,
    RefinedRequirement,
    RefineResult,
)
from app.features.maemusae.analysis.service import (
    AnalysisPlan,
    RefinePlan,
    RefineTarget,
    choose_plan,
    end_failed,
    load_pages,
    refine_plan,
)
from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents.models import READY
from app.llm import get_chat_model, invoke_structured, load_prompt
from app.llm.config import llm_settings

logger = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
KIND_GROUP = "MMS_REQ_KIND"
PRIORITY_GROUP = "MMS_PRIORITY"
DEFAULT_PRIORITY = "MEDIUM"
NO_INSTRUCTIONS = "(없음)"
FAILED_CODE = "ANALYSIS_FAILED"  # 킷 오류 코드가 없는 예외 (내용은 로그에 남기지 않음)

NAME_MAX = 200
QUOTE_MAX = 1000
DEDUPE_DESCRIPTION_CHARS = 80
DEDUPE_HEADROOM = 2000  # 합치기 프롬프트 지시문 몫으로 킷 입력 상한에서 빼 두는 글자 수
EXPAND_DESCRIPTION_CHARS = 300  # 보강에 보내는 설명 길이. 넘치면 이름만
EXPAND_CHUNK = 15  # 보강 AI 호출 1번에 볼 후보 수
EXPAND_HEADROOM = 4000  # 보강 프롬프트 지시문 몫
EXPAND_PER_SOURCE = 5  # 후보 하나에서 받는 숨은 요구사항 수 상한 (프롬프트와 같은 값)
HIDDEN_MARK = "[숨은 요구사항]"
DETAIL_CHUNK = 8  # 상세화 AI 호출 1번에 쓰는 후보 수. 답(명세) 길이가 이 수에 비례해 시간 초과를 막음
DETAIL_DESCRIPTION_CHARS = 600
DETAIL_QUOTE_CHARS = 300
NO_QUESTION = {"", "null", "none", "없음", "(없음)"}
# 다시 보내 볼 만한 오류 (킷 LLM 오류 코드). 설정 없음·입력 초과·키 오류는 다시 보내도 같으므로 제외
RETRYABLE_CODES = {"LLM_TIMEOUT", "LLM_RATE_LIMITED", "LLM_PROVIDER_ERROR", "LLM_BAD_OUTPUT"}
HEARTBEAT_SECONDS = 60
RETRY_BACKOFF_SECONDS = (5, 20)  # 다시 시도 전에 쉬는 시간 (일시 오류는 곧바로 다시 보내면 또 실패하기 쉬움)


@contextmanager
def _new_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


open_session = _new_session  # 테스트가 테스트 세션으로 바꿔 끼웁니다


@dataclass
class Candidate:
    name: str
    description: str
    kind: str
    priority: str
    question: str | None
    evidence: list[tuple[str, str]] = field(default_factory=list)  # (쪽 번호표, 문장)
    kind_defaulted: bool = False  # 목록에 없는 값이라 기본값을 넣음 (화면에 "확인 필요")
    priority_defaulted: bool = False
    category: CategoryPath = (None, None, None)  # 대·중·소분류 (업무 영역, M4-2)


def run_analysis(run_id: int) -> None:
    try:
        with open_session() as db:
            _run(db, run_id)
    except Exception as e:  # noqa: BLE001 — 실패 처리까지 실패한 경우 (DB 끊김 등). 멈춘 분석은 진행률을 읽을 때 정리됨
        logger.error("AI 분석 실패 처리 못함 run_id=%s error_type=%s", run_id, type(e).__name__)


def _run(db: Session, run_id: int) -> None:
    started = time.monotonic()
    run = repository.get_run(db, run_id)
    if run is None or run.status != RUNNING:
        return
    document_id = run.document_id
    try:
        plan = choose_plan(load_pages(db, document_id))
        candidates = _extract_all(db, run, plan, CategoryBook())  # 다시 분석은 기존 후보를 지우므로 빈 목록에서
        if plan.dedupe and len(candidates) > 1:
            candidates = _dedupe(candidates)
        if plan.expand and candidates:
            candidates = _expand(db, run, candidates)
        if plan.detail and candidates:
            candidates = _detail(db, run, candidates)
        count = _save(db, run_id, document_id, candidates, plan.by_tag)
    except Exception as e:  # noqa: BLE001 — 어느 단계 오류든 run 을 FAILED 로 남겨야 화면이 멈추지 않음
        db.rollback()
        code = e.code if isinstance(e, AppError) else FAILED_CODE
        _fail(db, run_id, document_id, code)
        logger.warning(
            "AI 분석 실패 run_id=%s document_id=%s code=%s error_type=%s ms=%d",
            run_id, document_id, code, type(e).__name__, (time.monotonic() - started) * 1000,
        )
        return
    if count is not None:
        logger.info(
            "AI 분석 끝 run_id=%s document_id=%s batches=%s requirements=%s ms=%d",
            run_id, document_id, len(plan.batches), count, (time.monotonic() - started) * 1000,
        )


def _code_text(db: Session, group: str) -> tuple[str, list[str]]:
    codes = list_codes(db, group)
    return ", ".join(f"{c.code}({c.label})" for c in codes), [c.code for c in codes]


def _stage_model(name: str):
    """단계별 모델 (MMS_EXTRACT_MODEL 등). 비우면 LLM_MODEL. 랭체인은 킷(app.llm)만 직접 다룸"""
    return get_chat_model(model_name=name.strip() or None)


def _retrying[T](call: Callable[[], T], step: str) -> Callable[[threading.Event], T]:
    """시간 초과·일시 오류면 이 호출만 MMS_BATCH_RETRIES 번까지 잠깐 쉬었다가 다시. 설정 오류·입력 초과는 바로 실패.

    stop 이 켜지면(다른 호출이 실패해 분석이 끝남) 더 보내지 않고 멈춤 (크레딧 낭비 방지)
    """

    def run(stop: threading.Event) -> T:
        attempt = 0
        while True:
            if stop.is_set():
                raise AnalysisCancelledError()
            try:
                return call()
            except AppError as e:
                if e.code not in RETRYABLE_CODES or attempt >= mms_settings.mms_batch_retries:
                    raise
                delay = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                attempt += 1
                cause = e.__cause__
                logger.warning(
                    "AI 분석 다시 시도 step=%s attempt=%s code=%s cause=%s status=%s wait=%ss",
                    step, attempt, e.code, type(cause).__name__ if cause else "-",
                    getattr(cause, "status_code", "-"), delay,
                )
                if stop.wait(delay):  # 쉬는 동안 분석이 끝나면 바로 멈춤
                    raise AnalysisCancelledError() from e

    return run


class AnalysisCancelledError(Exception):
    """다른 호출이 실패해 남은 호출을 멈춤 (밖으로는 처음 실패한 오류가 나감)"""


def _touch(db: Session, run: AnalysisRun) -> None:
    run.updated_at = datetime.now(UTC)
    db.commit()  # 오래 걸리는 호출을 기다리는 동안에도 멈춘 분석으로 보지 않게


def _call_all[T](db: Session, run: AnalysisRun, calls: list[Callable[[threading.Event], T]]) -> list[T]:
    """AI 호출을 MMS_ANALYZE_CONCURRENCY 개까지 동시에 보내고 결과를 calls 순서로 돌려줌.

    DB 는 이 함수(요청 스레드)에서만 씀. 기다리는 동안 HEARTBEAT_SECONDS 마다 진행 시각을 갱신.
    하나라도 실패하면 아직 시작하지 않은 호출은 취소하고 그 오류를 그대로 던짐.
    """
    workers = max(1, min(mms_settings.mms_analyze_concurrency, len(calls)))
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mms-analysis")
    stop = threading.Event()
    try:
        futures = [pool.submit(contextvars.copy_context().run, call, stop) for call in calls]  # 로그의 요청 id 유지
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=HEARTBEAT_SECONDS, return_when=FIRST_EXCEPTION)
            failed = next((f for f in futures if f in done and f.exception()), None)
            if failed:
                # 남은 호출을 기다리지 않고 바로 던짐 (기다리면 줄 선 호출이 모두 실행돼 한도만 더 씀)
                raise failed.exception()
            if pending:
                _touch(db, run)
        return [f.result() for f in futures]
    finally:
        stop.set()  # 아직 도는 호출은 다시 시도하지 않고 멈춤
        pool.shutdown(wait=False, cancel_futures=True)


def _extract_all(db: Session, run: AnalysisRun, plan: AnalysisPlan, book: CategoryBook) -> list[Candidate]:
    """묶음마다 후보 뽑기. MMS_ANALYZE_CONCURRENCY 개씩 한 차례로 동시에 보냄.

    앞 차례에서 쓴 분류 이름을 다음 차례에 같이 보내고, 같은 이름은 book 이 한 표기로 맞춤 (결과는 묶음 순서대로 처리).
    """
    kinds_text, kinds = _code_text(db, KIND_GROUP)
    priorities_text, priorities = _code_text(db, PRIORITY_GROUP)
    prompt = load_prompt(PROMPTS / "extract.md")
    model = _stage_model(mms_settings.mms_extract_model)
    wave = max(1, mms_settings.mms_analyze_concurrency)
    candidates: list[Candidate] = []
    for start in range(0, len(plan.batches), wave):
        batches = plan.batches[start : start + wave]
        categories = book.prompt_text()
        calls = [
            _retrying(
                partial(
                    invoke_structured,
                    prompt,
                    ExtractResult,
                    {
                        "kinds": kinds_text,
                        "priorities": priorities_text,
                        "instructions": run.prompt or NO_INSTRUCTIONS,
                        "categories": categories,
                        "document": batch.text,
                    },
                    model=model,
                ),
                f"extract-{start + i + 1}",
            )
            for i, batch in enumerate(batches)
        ]
        for batch, result in zip(batches, _call_all(db, run, calls), strict=True):
            for item in result.requirements:
                if c := _candidate(item, set(batch.tags), kinds, priorities):
                    c.category = book.canon((item.category_major, item.category_middle, item.category_minor))
                    candidates.append(c)
            run.done_steps += 1
        db.commit()  # 진행률. updated_at 이 바뀌어 멈춘 분석으로 보지 않음
    return candidates


def _question(value: str | None) -> str | None:
    """AI 가 질문 칸에 "null"·"없음"을 글자로 쓰는 일이 있어 빈 값으로 봄"""
    value = (value or "").strip()
    return None if value.lower() in NO_QUESTION else value


def _tag(value: str) -> str:
    value = value.strip().upper().strip("[]")
    return value if value.startswith("P") else f"P{value}"


def _candidate(item: ExtractedRequirement, tags: set[str], kinds: list[str], priorities: list[str]) -> Candidate | None:
    name = item.name.strip()[:NAME_MAX]
    if not name:
        return None
    # AI 가 목록에 없는 코드를 대면 첫 구분 / 보통으로 넣고 표시해 둠 (관리자가 검토 화면에서 바로 알아보고 고침)
    kind_defaulted = item.kind not in kinds
    kind = kinds[0] if kind_defaulted else item.kind
    priority_defaulted = item.priority not in priorities
    fallback = DEFAULT_PRIORITY if DEFAULT_PRIORITY in priorities else priorities[0]
    priority = fallback if priority_defaulted else item.priority
    evidence = []
    for ev in item.evidence:
        tag, quote = _tag(ev.page), ev.quote.strip()[:QUOTE_MAX]
        if tag in tags and quote and (tag, quote) not in evidence:  # 이 묶음에 없는 쪽 번호는 버림
            evidence.append((tag, quote))
    question = _question(item.question)
    return Candidate(
        name, item.description.strip(), kind, priority, question, evidence, kind_defaulted, priority_defaulted
    )


def _dedupe_lines(candidates: list[Candidate], with_description: bool) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        desc = c.description[:DEDUPE_DESCRIPTION_CHARS] if with_description else ""
        lines.append(f"{i}. {c.name}" + (f" - {desc}" if desc else ""))
    return "\n".join(lines)


def _dedupe(candidates: list[Candidate]) -> list[Candidate]:
    """이름·짧은 설명만 보내 같은 후보 묶음을 받음. 길면 이름만, 그래도 길면 합치기를 건너뜀"""
    budget = llm_settings.llm_max_input_chars - DEDUPE_HEADROOM
    text = _dedupe_lines(candidates, with_description=True)
    if len(text) > budget:
        text = _dedupe_lines(candidates, with_description=False)
    if len(text) > budget:
        logger.info("AI 분석 합치기 건너뜀 candidates=%s", len(candidates))
        return candidates
    result = invoke_structured(load_prompt(PROMPTS / "dedupe.md"), DedupeResult, {"candidates": text})

    merged_into: dict[int, int] = {}  # 후보 번호(0부터) → 남길 후보 번호
    for group in result.groups:
        ids = [i - 1 for i in dict.fromkeys(group) if 1 <= i <= len(candidates) and i - 1 not in merged_into]
        for i in ids[1:]:
            merged_into[i] = ids[0]
    kept = [c for i, c in enumerate(candidates) if i not in merged_into]
    for i, target in merged_into.items():
        # 앞 후보의 이름·설명·구분을 남기고 근거는 합침. 질문은 앞 후보에 없으면 가져옴
        keep, other = candidates[target], candidates[i]
        keep.evidence += [ev for ev in other.evidence if ev not in keep.evidence]
        keep.question = keep.question or other.question
        keep.category = keep.category if keep.category[0] else other.category
    return kept


def _expand_lines(candidates: list[Candidate], start: int, with_description: bool) -> str:
    lines = []
    for i, c in enumerate(candidates, start + 1):
        category = " > ".join(p for p in c.category if p)
        head = f"[{i}] {c.name} ({c.kind}, {c.priority}" + (f", {category}" if category else "") + ")"
        desc = " ".join(c.description.split())[:EXPAND_DESCRIPTION_CHARS] if with_description else ""
        lines.append(head + (f"\n    {desc}" if desc else ""))
    return "\n".join(lines)


def _name_key(name: str) -> str:
    return "".join(name.split()).lower()


def _expand(db: Session, run: AnalysisRun, candidates: list[Candidate]) -> list[Candidate]:
    """뽑은 목록을 EXPAND_CHUNK 개씩 보내 숨은 요구사항을 받아 출발한 후보 바로 뒤에 넣음.

    한 번에 다 보내면 AI 가 앞쪽 몇 개만 보고 마는 일이 많아 나눠 보냄. 겹치지 않게 전체 이름 목록도 같이 보냄.
    너무 길면(이름 목록만으로 상한을 넘으면) 보강을 건너뜀.
    """
    budget = llm_settings.llm_max_input_chars - EXPAND_HEADROOM
    names = "\n".join(f"[{i}] {c.name}" for i, c in enumerate(candidates, 1))
    if len(names) > budget:
        logger.info("AI 분석 보강 건너뜀 candidates=%s", len(candidates))
        return _step_done(db, run, candidates)
    kinds_text, kinds = _code_text(db, KIND_GROUP)
    priorities_text, priorities = _code_text(db, PRIORITY_GROUP)
    prompt = load_prompt(PROMPTS / "expand.md")
    model = _stage_model(mms_settings.mms_expand_model)
    starts = list(range(0, len(candidates), EXPAND_CHUNK))
    calls = []
    for start in starts:
        chunk = candidates[start : start + EXPAND_CHUNK]
        text = _expand_lines(chunk, start, with_description=True)
        if len(names) + len(text) > budget:
            text = _expand_lines(chunk, start, with_description=False)
        variables = {
            "kinds": kinds_text,
            "priorities": priorities_text,
            "instructions": run.prompt or NO_INSTRUCTIONS,
            "all_names": names,
            "requirements": text,
        }
        calls.append(_retrying(partial(invoke_structured, prompt, ExpandResult, variables, model=model), f"expand-{start + 1}"))
    items = []
    for start, result in zip(starts, _call_all(db, run, calls), strict=True):
        end = min(start + EXPAND_CHUNK, len(candidates))
        # 이번 조각 밖의 번호에서 출발한 것은 버림 (그 후보는 자기 조각에서 봄)
        items += [item for item in result.requirements if start < item.source <= end]

    seen = {_name_key(c.name) for c in candidates}
    added: dict[int, list[Candidate]] = {}  # 출발한 후보 번호(0부터) → 숨은 요구사항
    fallback = DEFAULT_PRIORITY if DEFAULT_PRIORITY in priorities else priorities[0]
    for item in items:
        name = item.name.strip()[:NAME_MAX]
        index = item.source - 1
        if not name or _name_key(name) in seen:
            continue  # 이미 있는 이름은 버림
        if len(added.setdefault(index, [])) >= EXPAND_PER_SOURCE:
            continue
        seen.add(_name_key(name))
        parent = candidates[index]
        description = item.description.strip()
        if not description.startswith(HIDDEN_MARK):
            description = f"{HIDDEN_MARK} '{parent.name}' 기능에 필요\n{description}".rstrip()
        kind_defaulted = item.kind not in kinds
        priority_defaulted = item.priority not in priorities
        added[index].append(
            Candidate(
                name,
                description,
                kinds[0] if kind_defaulted else item.kind,
                fallback if priority_defaulted else item.priority,
                _question(item.question),
                list(parent.evidence),  # 출발한 후보의 근거 (AI 가 지어낸 근거는 받지 않음)
                kind_defaulted,
                priority_defaulted,
                parent.category,
            )
        )
    expanded = []
    for i, c in enumerate(candidates):
        expanded.append(c)
        expanded += added.get(i, [])
    logger.info("AI 분석 보강 run_id=%s added=%s", run.id, len(expanded) - len(candidates))
    return _step_done(db, run, expanded)


def _detail_lines(candidates: list[Candidate], start: int) -> str:
    lines = []
    for i, c in enumerate(candidates, start + 1):
        category = " > ".join(p for p in c.category if p)
        lines.append(f"[{i}] {c.name} ({c.kind}, {c.priority}" + (f", {category}" if category else "") + ")")
        body = _hidden_split(c.description)[1]
        lines.append(f"    설명: {' '.join(body.split())[:DETAIL_DESCRIPTION_CHARS] or '(없음)'}")
        for _, quote in c.evidence[:2]:
            lines.append(f"    근거: \"{' '.join(quote.split())[:DETAIL_QUOTE_CHARS]}\"")
        if c.question:
            lines.append(f"    이미 있는 질문: {c.question}")
    return "\n".join(lines)


def _hidden_split(description: str) -> tuple[str | None, str]:
    """숨은 요구사항 첫 줄 표시와 나머지. 표시는 서버가 지켜서 AI 가 지우지 못하게 함"""
    if description.startswith(HIDDEN_MARK):
        head, _, rest = description.partition("\n")
        return head, rest.strip()
    return None, description


def _detail(db: Session, run: AnalysisRun, candidates: list[Candidate]) -> list[Candidate]:
    """후보를 DETAIL_CHUNK 개씩 보내 자세한 명세로 바꿈. 답이 없는 후보는 짧은 설명을 그대로 둠"""
    prompt = load_prompt(PROMPTS / "detail.md")
    model = _stage_model(mms_settings.mms_detail_model)
    starts = list(range(0, len(candidates), DETAIL_CHUNK))
    calls = [
        _retrying(
            partial(
                invoke_structured,
                prompt,
                DetailResult,
                {
                    "instructions": run.prompt or NO_INSTRUCTIONS,
                    "requirements": _detail_lines(candidates[start : start + DETAIL_CHUNK], start),
                },
                model=model,
            ),
            f"detail-{start + 1}",
        )
        for start in starts
    ]
    detailed = 0
    for start, result in zip(starts, _call_all(db, run, calls), strict=True):
        end = min(start + DETAIL_CHUNK, len(candidates))
        for item in result.items:
            body = item.description.strip()
            if not start < item.ref <= end or not body:
                continue  # 이번 조각 밖 번호·빈 답은 버림
            c = candidates[item.ref - 1]
            head, _ = _hidden_split(c.description)
            c.description = f"{head}\n{body}" if head else body
            c.question = c.question or _question(item.question)
            detailed += 1
    logger.info("AI 분석 상세화 run_id=%s candidates=%s detailed=%s", run.id, len(candidates), detailed)
    return _step_done(db, run, candidates)


def _step_done(db: Session, run: AnalysisRun, candidates: list[Candidate]) -> list[Candidate]:
    run.done_steps += 1
    db.commit()  # 진행률
    return candidates


def _save(
    db: Session, run_id: int, document_id: int, candidates: list[Candidate], by_tag: dict[str, PageRef]
) -> int | None:
    document = repository.lock_document(db, document_id)
    run = repository.get_run(db, run_id)
    if run is None or run.status != RUNNING:  # 그사이 멈춤 정리됨 → 저장하지 않음
        db.rollback()
        logger.warning("AI 분석 결과 버림 (이미 끝난 요청) run_id=%s", run_id)
        return None

    now = datetime.now(UTC)
    deleted = repository.delete_requirements(db, document_id)  # 처음 분석이면 지울 것이 없음
    _insert_candidates(db, document_id, 0, candidates, by_tag)
    repository.mark_sources_analyzed(db, document_id, run_id)
    run.status = SUCCEEDED
    run.done_steps = run.total_steps
    run.finished_at = now
    document.status = READY
    document.saved_at = None  # 새 분석이 시작됐으므로 다음 '버전 저장'은 새 버전을 만듦
    document.saved_by = None
    db.commit()
    if deleted:
        logger.info("AI 분석 이전 후보 지움 run_id=%s document_id=%s deleted=%s", run_id, document_id, deleted)
    return len(candidates)


def _sources(
    requirement_id: int, evidence: list[tuple[str, str]], by_tag: dict[str, PageRef], start_order: int = 0
) -> list[RequirementSource]:
    """근거 문장을 쪽 본문에서 찾아 확인 표시·끝 쪽을 정함"""
    index = {tag: i for i, tag in enumerate(by_tag, 1)}
    rows = []
    for order, (tag, quote) in enumerate(evidence, start_order + 1):
        page = by_tag[tag]
        found, end_page = locate(quote, page, by_tag.get(tag_of(index[tag] + 1)))
        rows.append(
            RequirementSource(
                requirement_id=requirement_id,
                source_page_id=page.id,
                end_source_page_id=end_page.id if end_page else None,
                quote=quote,
                verified=found,
                sort_order=order,
            )
        )
    return rows


def _insert_candidates(
    db: Session, document_id: int, last_seq: int, candidates: list[Candidate], by_tag: dict[str, PageRef]
) -> None:
    for seq, c in enumerate(candidates, last_seq + 1):
        requirement = Requirement(
            document_id=document_id,
            seq=seq,
            name=c.name,
            kind=c.kind,
            priority=c.priority,
            description=c.description,
            ai_question=c.question,
            kind_defaulted=c.kind_defaulted,
            priority_defaulted=c.priority_defaulted,
            category_major=c.category[0],
            category_middle=c.category[1],
            category_minor=c.category[2],
        )
        repository.add(db, requirement)
        repository.add_all(db, _sources(requirement.id, c.evidence, by_tag))


def _fail(db: Session, run_id: int, document_id: int, code: str) -> None:
    document = repository.lock_document(db, document_id)
    run = repository.get_run(db, run_id)
    if run is None or run.status != RUNNING or document is None:
        db.rollback()
        return
    end_failed(db, run, document, code)
    db.commit()


# ---- 다시 분류 (M3-3) ----
#
# 1. 반영 안 된 입력이 달린 후보를 묶음마다 prompts/refine.md 로 보내 바꿀 칸을 받음 (입력은 "입력 1, 입력 2", 이름 X)
# 2. 새 파일이 있으면 처음 분석과 같은 방식으로 후보를 뽑고, 이름이 비슷한 기존 후보와 함께 prompts/dedupe.md 로
#    같은 후보를 찾음. 기존과 같으면 그 후보에 근거만 더하고, 새 내용이면 다음 번호로 추가
# 3. 저장할 때 그사이 사람이 고친 후보(version 다름)는 AI 수정을 건너뛰고 그 입력은 다음 분류로 남김 (사람 우선)
# 후보 번호·id 는 그대로, 버전 번호·saved_at 은 건드리지 않습니다.

MATCH_PER_CANDIDATE = 5  # 새 후보마다 함께 보낼 비슷한 기존 후보 수
MATCH_MAX_EXISTING = 60


def run_refine(run_id: int) -> None:
    try:
        with open_session() as db:
            _run_refine(db, run_id)
    except Exception as e:  # noqa: BLE001 — run_analysis 와 같은 이유
        logger.error("AI 다시 분류 실패 처리 못함 run_id=%s error_type=%s", run_id, type(e).__name__)


def _run_refine(db: Session, run_id: int) -> None:
    started = time.monotonic()
    run = repository.get_run(db, run_id)
    if run is None or run.status != RUNNING:
        return
    document_id = run.document_id
    try:
        plan = refine_plan(db, document_id)
        run.total_steps = plan.total_steps  # 시작 뒤 입력이 늘었을 수 있음
        db.commit()
        book = CategoryBook(repository.list_category_paths(db, document_id))
        updates = _ask_refine(db, run, plan.chunks, book)
        new_candidates: list[Candidate] = []
        merges: dict[int, list[tuple[str, str]]] = {}
        if plan.extract:
            new_candidates = _extract_all(db, run, plan.extract, book)
            new_candidates, merges = _match(repository.list_live_requirements(db, document_id), new_candidates)
            run.done_steps += 1
            db.commit()
        result = _save_refine(db, run_id, document_id, plan, updates, new_candidates, merges, book)
    except Exception as e:  # noqa: BLE001 — 어느 단계 오류든 run 을 FAILED 로 남겨야 화면이 멈추지 않음
        db.rollback()
        code = e.code if isinstance(e, AppError) else FAILED_CODE
        _fail(db, run_id, document_id, code)
        logger.warning(
            "AI 다시 분류 실패 run_id=%s document_id=%s code=%s error_type=%s ms=%d",
            run_id, document_id, code, type(e).__name__, (time.monotonic() - started) * 1000,
        )
        return
    if result is not None:
        changed, skipped, added, merged = result
        logger.info(
            "AI 다시 분류 끝 run_id=%s document_id=%s changed=%s skipped=%s added=%s merged=%s ms=%d",
            run_id, document_id, changed, skipped, added, merged, (time.monotonic() - started) * 1000,
        )


def _ask_refine(
    db: Session, run: AnalysisRun, chunks: list[list[RefineTarget]], book: CategoryBook
) -> dict[str, RefinedRequirement]:
    if not chunks:
        return {}
    kinds_text, _ = _code_text(db, KIND_GROUP)
    priorities_text, _ = _code_text(db, PRIORITY_GROUP)
    prompt = load_prompt(PROMPTS / "refine.md")
    updates: dict[str, RefinedRequirement] = {}
    for chunk in chunks:
        tags = {t.tag for t in chunk}
        result = invoke_structured(
            prompt,
            RefineResult,
            {
                "kinds": kinds_text,
                "priorities": priorities_text,
                "instructions": run.prompt or NO_INSTRUCTIONS,
                "categories": book.prompt_text(),
                "targets": "\n\n".join(t.text for t in chunk),
            },
        )
        for update in result.updates:
            tag = _ref(update.ref)
            if tag in tags:  # 이 묶음에 없는 번호표는 버림
                updates[tag] = update
        run.done_steps += 1
        db.commit()
    return updates


def _ref(value: str) -> str:
    value = value.strip().upper().strip("[]")
    return value if value.startswith("R") else f"R{value}"


def _bigrams(value: str) -> set[str]:
    text = normalize(value).replace(" ", "")
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _related(existing: list[Requirement], candidates: list[Candidate]) -> list[Requirement]:
    """새 후보마다 이름·설명이 비슷한 기존 후보 몇 개 (글자 두 개씩 겹치는 정도). 전체를 보내지 않으려고"""
    grams = {r.id: _bigrams(f"{r.name} {r.description[:DEDUPE_DESCRIPTION_CHARS]}") for r in existing}
    picked: set[int] = set()
    for c in candidates:
        mine = _bigrams(f"{c.name} {c.description[:DEDUPE_DESCRIPTION_CHARS]}")
        scored = sorted(
            ((len(mine & g) / len(mine | g), rid) for rid, g in grams.items() if mine and g and mine & g), reverse=True
        )
        picked.update(rid for _, rid in scored[:MATCH_PER_CANDIDATE])
    return [r for r in existing if r.id in picked][:MATCH_MAX_EXISTING]


def _match(
    existing: list[Requirement], candidates: list[Candidate]
) -> tuple[list[Candidate], dict[int, list[tuple[str, str]]]]:
    """(새로 추가할 후보, 기존 후보 id → 더할 근거). 새 후보끼리 같은 것도 하나로 합침"""
    if not candidates:
        return [], {}
    related = _related(existing, candidates)
    lines = [
        f"{i}. (기존 REQ-{r.seq:03d}) {r.name} - {r.description[:DEDUPE_DESCRIPTION_CHARS]}"
        for i, r in enumerate(related, 1)
    ]
    offset = len(related)
    lines += [
        f"{offset + i}. {c.name} - {c.description[:DEDUPE_DESCRIPTION_CHARS]}" for i, c in enumerate(candidates, 1)
    ]
    text = "\n".join(lines)
    if len(text) > llm_settings.llm_max_input_chars - DEDUPE_HEADROOM or len(lines) < 2:
        logger.info("AI 다시 분류 맞춰 보기 건너뜀 candidates=%s existing=%s", len(candidates), len(related))
        return candidates, {}
    result = invoke_structured(load_prompt(PROMPTS / "dedupe.md"), DedupeResult, {"candidates": text})

    used: set[int] = set()
    into_existing: dict[int, int] = {}  # 새 후보 번호(0부터) → 기존 후보 id
    into_new: dict[int, int] = {}  # 새 후보 번호 → 남길 새 후보 번호
    for group in result.groups:
        ids = [i for i in dict.fromkeys(group) if 1 <= i <= len(lines) and i not in used]
        olds = [i for i in ids if i <= offset]
        news = [i - offset - 1 for i in ids if i > offset]
        if not news:
            continue  # 기존끼리 같은 것은 사람이 정리 (다시 분류가 기존 후보를 지우지 않음)
        used.update(ids)
        if olds:
            for n in news:
                into_existing[n] = related[olds[0] - 1].id
        else:
            for n in news[1:]:
                into_new[n] = news[0]
    merges: dict[int, list[tuple[str, str]]] = {}
    for n, rid in into_existing.items():
        evidence = merges.setdefault(rid, [])
        evidence += [ev for ev in candidates[n].evidence if ev not in evidence]
    for n, target in into_new.items():
        keep, other = candidates[target], candidates[n]
        keep.evidence += [ev for ev in other.evidence if ev not in keep.evidence]
        keep.question = keep.question or other.question
        keep.category = keep.category if keep.category[0] else other.category
    kept = [c for i, c in enumerate(candidates) if i not in into_existing and i not in into_new]
    return kept, merges


def _apply_refine(
    requirement: Requirement, update: RefinedRequirement, kinds: list[str], priorities: list[str], book: CategoryBook
) -> bool:
    """AI 가 준 칸 반영. 목록에 없는 구분·우선순위는 무시 (처음 분석과 달리 기존 값이 있으므로 기본값을 넣지 않음).
    분류는 비어 있는 후보에만 채움: 이미 있는 분류(AI 가 넣었든 사람이 고쳤든)는 바꾸지 않음 (계획 19 1-7)"""
    changes: dict = {}
    if requirement.category_major is None:
        major, middle, minor = book.canon((update.category_major, update.category_middle, update.category_minor))
        if major:
            changes.update(category_major=major, category_middle=middle, category_minor=minor)
    name = (update.name or "").strip()[:NAME_MAX]
    if name and name != requirement.name:
        changes["name"] = name
    if update.description is not None and update.description.strip() != requirement.description:
        changes["description"] = update.description.strip()
    if update.kind in kinds and update.kind != requirement.kind:
        changes.update(kind=update.kind, kind_defaulted=False)
    if update.priority in priorities and update.priority != requirement.priority:
        changes.update(priority=update.priority, priority_defaulted=False)
    question = _question(update.question)
    if update.clear_question and requirement.ai_question and not question:
        changes["ai_question"] = None
    if question and question != requirement.ai_question:
        changes["ai_question"] = question
    answer = (update.answer or "").strip() or None
    if answer and answer != requirement.ai_answer:
        changes["ai_answer"] = answer
    for key, value in changes.items():
        setattr(requirement, key, value)
    return bool(changes)


def _save_refine(
    db: Session,
    run_id: int,
    document_id: int,
    plan: RefinePlan,
    updates: dict[str, RefinedRequirement],
    new_candidates: list[Candidate],
    merges: dict[int, list[tuple[str, str]]],
    book: CategoryBook,
) -> tuple[int, int, int, int] | None:
    """(고친 후보, 건너뛴 후보, 새 후보, 근거를 더한 후보) 수"""
    document = repository.lock_document(db, document_id)
    run = repository.get_run(db, run_id)
    if run is None or run.status != RUNNING:
        db.rollback()
        logger.warning("AI 다시 분류 결과 버림 (이미 끝난 요청) run_id=%s", run_id)
        return None

    _, kinds = _code_text(db, KIND_GROUP)
    _, priorities = _code_text(db, PRIORITY_GROUP)
    targets = [t for chunk in plan.chunks for t in chunk]
    rows = repository.lock_requirements(db, document_id, sorted({t.requirement_id for t in targets} | set(merges)))
    changed = skipped = 0
    seen: dict[int, datetime] = {}
    for target in targets:
        requirement = rows.get(target.requirement_id)
        if requirement is None or requirement.deleted_at is not None or requirement.version != target.version:
            skipped += 1  # 그사이 사람이 고치거나 지움 → 사람 수정 우선, 입력은 다음 분류로
            continue
        update = updates.get(target.tag)
        if update is not None and _apply_refine(requirement, update, kinds, priorities, book):
            requirement.version += 1
            requirement.updated_by = run.requested_by
            changed += 1
        seen.update(target.notes)
    for note in repository.lock_notes(db, list(seen)):
        if note.applied_run_id is None and note.updated_at == seen[note.id]:  # 그사이 고친 입력은 다음 분류로
            note.applied_run_id = run.id

    by_tag = plan.extract.by_tag if plan.extract else {}
    orders = repository.max_sort_orders(db, list(merges))
    merged = 0
    for requirement_id, evidence in merges.items():
        requirement = rows.get(requirement_id)
        if requirement is None or requirement.deleted_at is not None or not evidence:
            continue
        repository.add_all(db, _sources(requirement_id, evidence, by_tag, orders.get(requirement_id, 0)))
        merged += 1
    _insert_candidates(db, document_id, repository.max_seq(db, document_id), new_candidates, by_tag)
    if plan.new_source_ids:
        repository.mark_sources_analyzed(db, document_id, run_id, source_ids=plan.new_source_ids)
    run.status = SUCCEEDED
    run.done_steps = run.total_steps
    run.finished_at = datetime.now(UTC)
    document.status = READY
    db.commit()
    return changed, skipped, len(new_candidates), merged

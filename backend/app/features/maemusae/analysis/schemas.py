from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---- AI 응답 모양 (invoke_structured 가 이 모양으로 받음) ----


class ExtractedEvidence(BaseModel):
    page: str = Field(description="근거가 있는 쪽의 번호표. 쪽 앞 [P3 · …] 의 P3")
    quote: str = Field(description="그 쪽 본문에서 고치지 않고 그대로 옮긴 문장")


class ExtractedRequirement(BaseModel):
    name: str = Field(description="짧은 이름 (예: 이메일 회원가입)")
    description: str = Field(default="", description="무엇을 해야 하는지 한두 문장")
    kind: str = Field(description="구분 코드")
    priority: str = Field(description="우선순위 코드")
    category_major: str | None = Field(default=None, description="대분류 (업무 영역, 예: 회원 관리). 모르면 null")
    category_middle: str | None = Field(default=None, description="중분류 (예: 로그인). 모르면 null")
    category_minor: str | None = Field(default=None, description="소분류 (예: 소셜 로그인). 모르면 null")
    question: str | None = Field(default=None, description="모호하거나 서로 다르면 고객에게 물을 질문 한 문장, 아니면 null")
    evidence: list[ExtractedEvidence] = Field(default_factory=list)


class ExtractResult(BaseModel):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)


class RefinedRequirement(BaseModel):
    ref: str = Field(description="후보 번호표. [R1 · REQ-002 …] 의 R1")
    name: str | None = Field(default=None, description="바꿀 이름. 그대로면 null")
    description: str | None = Field(default=None, description="바꿀 설명. 그대로면 null")
    kind: str | None = Field(default=None, description="바꿀 구분 코드. 그대로면 null")
    priority: str | None = Field(default=None, description="바꿀 우선순위 코드. 그대로면 null")
    category_major: str | None = Field(default=None, description="분류가 (없음)인 후보에만: 대분류. 아니면 null")
    category_middle: str | None = Field(default=None, description="분류가 (없음)인 후보에만: 중분류. 아니면 null")
    category_minor: str | None = Field(default=None, description="분류가 (없음)인 후보에만: 소분류. 아니면 null")
    question: str | None = Field(default=None, description="새로 남길 질문 (입력끼리 다를 때 등). 없으면 null")
    clear_question: bool = Field(default=False, description="입력이 기존 AI 질문에 답했으면 true")
    answer: str | None = Field(default=None, description="질문에 대한 답을 한두 문장으로 정리. 없으면 null")


class RefineResult(BaseModel):
    updates: list[RefinedRequirement] = Field(default_factory=list, description="바꿀 후보만. 바꿀 것이 없는 후보는 빼도 됨")


class DedupeResult(BaseModel):
    groups: list[list[int]] = Field(default_factory=list, description="같은 요구사항끼리 묶은 후보 번호 (묶음마다 2개 이상)")


# ---- API ----


class AnalyzeRequest(BaseModel):
    prompt: str | None = Field(
        default=None, max_length=2000, description="AI 에게 덧붙일 지시 (예: 관리자 기능 위주로)", examples=["결제 관련 내용을 꼼꼼히 봐 줘"]
    )
    restart: bool = Field(
        default=False,
        description="후보가 있는 문서를 다시 분석 (후보·직접 추가·입력을 모두 지우고 REQ-001 부터, 10/29 결정)",
    )


class RefineRequest(BaseModel):
    prompt: str | None = Field(
        default=None, max_length=2000, description="AI 에게 덧붙일 지시", examples=["보안 요구사항을 더 꼼꼼히 봐 줘"]
    )


class AnalysisStarted(BaseModel):
    run_id: int = Field(examples=[3])


class AnalysisRunRead(BaseModel):
    """마지막 분석 요청. 화면은 RUNNING 동안 2~3초마다 읽어 "3/10 분석 중"을 보여 줍니다."""

    run_id: int = Field(examples=[3])
    run_type: Literal["ANALYZE", "REFINE"] = Field(examples=["ANALYZE"])
    status: Literal["RUNNING", "SUCCEEDED", "FAILED"] = Field(examples=["RUNNING"])
    done_steps: int = Field(examples=[3])
    total_steps: int = Field(description="묶음 수 (+ 묶음이 여럿이면 합치기 1)", examples=[10])
    error_code: str | None = Field(default=None, description="실패 이유 (예: LLM_TIMEOUT, ANALYSIS_INTERRUPTED)")
    started_at: datetime
    finished_at: datetime | None = None

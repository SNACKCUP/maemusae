"""AI 분석 요청·요구사항 후보·근거 테이블.

    mms_documents ──< mms_analysis_runs          분석 요청 한 번 (처음 분석·다시 분류)
                  ──< mms_requirements ──< mms_requirement_sources ──> mms_source_pages
                      REQ-001 후보          근거: 어느 쪽의 어떤 문장

- 상태·종류(status, run_type)는 코드가 흐름을 바꾸는 값이라 CHECK, 구분·우선순위는 공통코드(MMS_REQ_KIND·MMS_PRIORITY)
- 토큰 수·비용 칸은 두지 않습니다 (규칙 3장: 사용량 기록은 이번 범위 밖)
- 같은 문서에 분석이 둘 돌지 않게 RUNNING 은 문서마다 하나 (부분 유니크 인덱스)
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin

ANALYZE = "ANALYZE"  # 처음 분류 (또는 처음부터 다시)
REFINE = "REFINE"  # 다시 분류 (M3-3)

RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"


class AnalysisRun(TimestampMixin, Base):
    __tablename__ = "mms_analysis_runs"
    __table_args__ = (
        CheckConstraint("run_type IN ('ANALYZE', 'REFINE')", name="ck_mms_analysis_runs_run_type"),
        CheckConstraint("status IN ('RUNNING', 'SUCCEEDED', 'FAILED')", name="ck_mms_analysis_runs_status"),
        Index(
            "uq_mms_analysis_runs_document_running",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("mms_documents.id", ondelete="CASCADE"), index=True)
    run_type: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str | None] = mapped_column(Text)  # 사용자가 적은 지시문 (고객 정보일 수 있어 로그 금지)
    status: Mapped[str] = mapped_column(String(20), server_default=RUNNING)
    error_code: Mapped[str | None] = mapped_column(String(50))  # 실패 이유 (킷 LLM 오류 코드 그대로)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_steps: Mapped[int] = mapped_column(Integer, server_default="1")  # 묶음 수 (+ 합치기 1)
    done_steps: Mapped[int] = mapped_column(Integer, server_default="0")  # 화면의 "3/10 분석 중"
    # updated_at(TimestampMixin)은 단계가 끝날 때마다 바뀌어, 오래 그대로면 멈춘 분석으로 봅니다


class Requirement(TimestampMixin, Base):
    __tablename__ = "mms_requirements"
    __table_args__ = (
        # 문서 안 번호. 응답의 code 는 REQ- + 세 자리. 지운 후보 번호는 다시 쓰지 않음
        UniqueConstraint("document_id", "seq", name="uq_mms_requirements_document_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("mms_documents.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # 공통코드 MMS_REQ_KIND
    priority: Mapped[str] = mapped_column(String(30))  # 공통코드 MMS_PRIORITY
    # 대·중·소분류 = 업무 영역 (예: 회원 관리 > 로그인 > 소셜 로그인). AI 가 채우고 사람이 고침. 프로젝트마다 다른 글이라
    # 공통코드가 아님 (10/29 SoYoung 결정 F, 계획 19 M4-2). 비어 있을 수 있음
    category_major: Mapped[str | None] = mapped_column(String(100))
    category_middle: Mapped[str | None] = mapped_column(String(100))
    category_minor: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, server_default="")
    ai_question: Mapped[str | None] = mapped_column(Text)  # 있으면 화면에 "확인 필요"
    ai_answer: Mapped[str | None] = mapped_column(Text)
    is_manual: Mapped[bool] = mapped_column(Boolean, server_default="false")  # 직접 추가한 후보 (이것만 삭제 가능)
    is_included: Mapped[bool] = mapped_column(Boolean, server_default="true")  # 체크 해제하면 확정에서 빠짐
    # AI 가 목록에 없는 값을 답해서 서버가 기본값(첫 구분 / 보통)을 넣었으면 true. 화면이 그 칸에 "확인 필요"를 붙이고,
    # 사람이 그 칸을 고치거나 그대로 확정하면 false (M3-2 수정 API). 10/29 SoYoung 결정 B
    kind_defaulted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    priority_defaulted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # AI 가 만들면 비움
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")  # 고칠 때마다 +1 (동시 수정 확인)


class RequirementSource(Base):
    __tablename__ = "mms_requirement_sources"
    __table_args__ = (
        CheckConstraint(
            "end_source_page_id IS NULL OR end_source_page_id <> source_page_id",
            name="ck_mms_requirement_sources_end_page",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("mms_requirements.id", ondelete="CASCADE"), index=True)
    # 어느 파일의 어느 쪽인지 (파일 이름은 쪽에서 따라감). 문장이 여러 쪽에 걸치면 시작 쪽
    source_page_id: Mapped[int] = mapped_column(ForeignKey("mms_source_pages.id", ondelete="CASCADE"), index=True)
    # 문장이 다음 쪽으로 넘어가면 끝 쪽 (같은 파일의 바로 다음 쪽만). 화면 위치는 3~4쪽
    end_source_page_id: Mapped[int | None] = mapped_column(ForeignKey("mms_source_pages.id", ondelete="CASCADE"))
    quote: Mapped[str] = mapped_column(Text)  # 근거 문장 (고객 문서, 로그 금지)
    verified: Mapped[bool] = mapped_column(Boolean)  # 서버가 그 쪽 본문에서 찾았으면 true
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

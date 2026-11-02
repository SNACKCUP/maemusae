"""입력한 내용 테이블 (요구사항 후보에 멤버가 남기는 설명 수정·AI 질문 답변).

    mms_requirements ──< mms_requirement_notes >── users
                         사람마다 칸마다 한 건 (10/28 결정 5)

- field 는 코드가 흐름을 바꾸는 값이라 CHECK (DESCRIPTION 설명 / ANSWER AI 질문 답변)
- applied_run_id: 다시 분류(M3-3)에 반영된 분석 요청. 비어 있으면 아직 반영 전, 글을 고치면 다시 비움
"""

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin

DESCRIPTION = "DESCRIPTION"
ANSWER = "ANSWER"


class RequirementNote(TimestampMixin, Base):
    __tablename__ = "mms_requirement_notes"
    __table_args__ = (
        CheckConstraint("field IN ('DESCRIPTION', 'ANSWER')", name="ck_mms_requirement_notes_field"),
        UniqueConstraint("requirement_id", "field", "author_id", name="uq_mms_requirement_notes_requirement_field_author"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 후보로 찾는 조회는 UNIQUE(requirement_id, …) 인덱스가 맡음
    requirement_id: Mapped[int] = mapped_column(ForeignKey("mms_requirements.id", ondelete="CASCADE"))
    field: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)  # 고객 프로젝트 내용일 수 있어 로그 금지
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    applied_run_id: Mapped[int | None] = mapped_column(ForeignKey("mms_analysis_runs.id", ondelete="SET NULL"))

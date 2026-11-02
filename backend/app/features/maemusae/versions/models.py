"""버전 기록 테이블 (10/29 SoYoung 결정, 계획 17의 2-1). 09 설계의 mms_document_revisions 를 대신합니다.

    mms_documents ──< mms_document_versions
                      SAVED: 버전 추가·버전 저장 (v1, v2…) / CONFIRMED: 확정 (M4)

- items 는 그 순간의 후보·근거·입력 전체를 JSON 으로 복사 (쌍둥이 테이블 대신). 이후 후보를 고치거나
  다시 분석해도 바뀌지 않음. 고객 프로젝트 내용이라 로그 금지
- 버전 저장으로 덮어쓰면 updated_by·updated_at 이 바뀜
- 버전 번호는 SAVED 만, 확정 번호는 CONFIRMED 만 가짐 (CHECK)
"""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.models import TimestampMixin

SAVED = "SAVED"
CONFIRMED = "CONFIRMED"


class DocumentVersion(TimestampMixin, Base):
    __tablename__ = "mms_document_versions"
    __table_args__ = (
        CheckConstraint("kind IN ('SAVED', 'CONFIRMED')", name="ck_mms_document_versions_kind"),
        CheckConstraint("(kind = 'SAVED') = (version_no IS NOT NULL)", name="ck_mms_document_versions_version_no"),
        CheckConstraint("(kind = 'CONFIRMED') = (revision IS NOT NULL)", name="ck_mms_document_versions_revision"),
        Index(
            "uq_mms_document_versions_saved_no",
            "document_id",
            "version_no",
            unique=True,
            postgresql_where=text("kind = 'SAVED'"),
        ),
        Index(
            "uq_mms_document_versions_confirmed_revision",
            "document_id",
            "revision",
            unique=True,
            postgresql_where=text("kind = 'CONFIRMED'"),
        ),
        Index("ix_mms_document_versions_document_created", "document_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("mms_documents.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    version_no: Mapped[int | None] = mapped_column(Integer)  # v1, v2… (SAVED)
    revision: Mapped[int | None] = mapped_column(Integer)  # 확정 번호 (CONFIRMED, M4)
    title: Mapped[str] = mapped_column(String(200))
    item_count: Mapped[int] = mapped_column(Integer)
    items: Mapped[list] = mapped_column(JSONB)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # 버전 저장으로 덮어쓴 사람

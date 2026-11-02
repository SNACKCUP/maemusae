"""문서·올린 파일·쪽 단위 본문 테이블.

    mms_projects ──< mms_documents ──< mms_source_files ──< mms_source_pages
                     파일 카드          올린 파일·직접 쓴 글    쪽(위치)마다 마크다운 본문

- 문서 종류(kind)는 공통코드 MMS_DOC_KIND, 상태(status)는 코드가 흐름을 바꾸는 값이라 CHECK 입니다.
- 원본 파일은 비공개 저장소(app.storage.get_private_storage)에 두고 여기에는 storage_key 만 둡니다.
- 본문은 MarkItDown 으로 바꾼 마크다운을 쪽 그대로 나눠 둡니다. 쪽을 넘어가는 문장은 쓰는 쪽(M3)에서 이어 붙입니다.
- analysis_run_id: 어느 분석 요청에 들어갔는지 (M3). 비어 있으면 아직 분석하지 않은 파일 (다시 분류 때 새 파일로 봄)
"""

from datetime import datetime

from sqlalchemy import (
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

REQUIREMENTS = "REQUIREMENTS"  # 요구사항정의서 (공통코드 MMS_DOC_KIND). 프로젝트를 만들 때 이 문서 1행을 만듦

EMPTY = "EMPTY"  # 시작 전
ANALYZING = "ANALYZING"  # AI 분석 중 (M3)
READY = "READY"  # 확정 대기
CONFIRMING = "CONFIRMING"  # 확정 중 (M4)
CONFIRMED = "CONFIRMED"  # 확정됨
FAILED = "FAILED"  # 분석 실패
BUSY_STATUSES = (ANALYZING, CONFIRMING)  # 이 상태에서는 파일을 올리거나 지울 수 없음

FILE = "FILE"  # 올린 파일 (원본은 비공개 저장소)
TEXT = "TEXT"  # 직접 쓴 글 (원본 없음, 본문 1행)
PARSED = "PARSED"


class Document(TimestampMixin, Base):
    __tablename__ = "mms_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", name="uq_mms_documents_project_kind"),  # 프로젝트마다 종류별 하나
        CheckConstraint(
            "status IN ('EMPTY', 'ANALYZING', 'READY', 'CONFIRMING', 'CONFIRMED', 'FAILED')",
            name="ck_mms_documents_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("mms_projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))  # 공통코드 MMS_DOC_KIND
    status: Mapped[str] = mapped_column(String(20), server_default=EMPTY)
    current_revision: Mapped[int] = mapped_column(Integer, server_default="0")  # 마지막 확정 번호 (M4)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 이번 분석 이후 마지막 버전 추가·저장 (다시 분석하면 비움, 10/29)
    saved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class SourceFile(Base):
    __tablename__ = "mms_source_files"
    __table_args__ = (
        CheckConstraint("source_type IN ('FILE', 'TEXT')", name="ck_mms_source_files_source_type"),
        CheckConstraint("parse_status IN ('PARSED', 'FAILED')", name="ck_mms_source_files_parse_status"),
        # 올린 파일이면 이름·형식·크기·해시·원본 위치가 모두 있어야 함
        CheckConstraint(
            "source_type = 'TEXT' OR (filename IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL"
            " AND sha256 IS NOT NULL AND storage_key IS NOT NULL)",
            name="ck_mms_source_files_file_fields",
        ),
        # 같은 문서에 같은 파일을 두 번 올리지 않게 (동시에 올려도)
        Index(
            "uq_mms_source_files_document_sha256",
            "document_id",
            "sha256",
            unique=True,
            postgresql_where=text("sha256 IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("mms_documents.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(10))
    filename: Mapped[str | None] = mapped_column(String(255))  # 원래 파일 이름 (로그·저장소 key 에는 넣지 않음)
    content_type: Mapped[str | None] = mapped_column(String(100))  # 확장자로 정한 형식 (브라우저가 보낸 값은 믿지 않음)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_key: Mapped[str | None] = mapped_column(String(300))  # 비공개 저장소 key
    page_count: Mapped[int] = mapped_column(Integer, server_default="0")
    parse_status: Mapped[str] = mapped_column(String(20), server_default=PARSED)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    analysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("mms_analysis_runs.id", ondelete="SET NULL", name="fk_mms_source_files_analysis_run_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourcePage(Base):
    __tablename__ = "mms_source_pages"
    __table_args__ = (UniqueConstraint("source_file_id", "seq", name="uq_mms_source_pages_file_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("mms_source_files.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)  # 파일 안 순서 (1부터). "다음 쪽"은 seq + 1
    page_no: Mapped[int | None] = mapped_column(Integer)  # 진짜 쪽 번호가 있을 때만 (PDF 쪽, PPT 슬라이드)
    location_label: Mapped[str] = mapped_column(String(200))  # 화면 표시: 3쪽, 슬라이드 4, 시트 '요구사항', 직접 입력
    text: Mapped[str] = mapped_column(Text)  # 그 위치의 마크다운 본문 (고객 문서, 로그 금지)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

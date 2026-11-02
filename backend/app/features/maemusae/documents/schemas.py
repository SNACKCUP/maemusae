from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["EMPTY", "ANALYZING", "READY", "CONFIRMING", "CONFIRMED", "FAILED"]


class DocumentRead(BaseModel):
    """파일 카드 하나 (요구사항정의서 등)."""

    id: int = Field(examples=[1])
    kind: str = Field(description="공통코드 MMS_DOC_KIND", examples=["REQUIREMENTS"])
    kind_label: str = Field(description="화면 이름 (공통코드 label)", examples=["요구사항정의서"])
    status: DocumentStatus = Field(examples=["EMPTY"])
    current_revision: int = Field(description="마지막 확정 번호 (확정 전 0)", examples=[0])
    source_count: int = Field(description="올린 파일·직접 쓴 글 수", examples=[2])
    saved_at: datetime | None = Field(
        default=None, description="이번 분석 이후 마지막으로 버전 추가·저장한 시각. 다시 분석하면 null (10/29)"
    )
    last_version_no: int | None = Field(default=None, description="마지막 버전 번호 (화면 '마지막 버전 v2'). 없으면 null")
    changed_since_save: bool = Field(default=False, description="saved_at 뒤에 후보·입력을 또 고쳤으면 true")
    manual_count: int = Field(default=0, description="직접 추가한 후보 수 (다시 분석하면 사라짐)")
    open_question_count: int = Field(
        default=0, description="체크된 후보 중 답이 없는 AI 질문 수. 확정 창 경고용 (막지는 않음)"
    )
    defaulted_count: int = Field(default=0, description="체크된 후보 중 'AI 값 확인' 표시가 남은 수. 확정 창 경고용")
    confirmed_at: datetime | None = None
    confirmed_by_name: str | None = Field(default=None, examples=["이소영"])
    updated_at: datetime


class SourceRead(BaseModel):
    """올린 파일 또는 직접 쓴 글. 본문은 /pages, 원본은 /file 로 따로 받습니다."""

    id: int = Field(examples=[7])
    source_type: Literal["FILE", "TEXT"] = Field(examples=["FILE"])
    filename: str | None = Field(description="직접 쓴 글이면 null", examples=["쇼핑몰_요청서.pdf"])
    content_type: str | None = Field(examples=["application/pdf"])
    size_bytes: int | None = Field(examples=[482113])
    page_count: int = Field(description="나눈 쪽(위치) 수", examples=[12])
    uploaded_by_name: str = Field(examples=["이소영"])
    uploaded_by_me: bool = Field(description="내가 올렸는지 (지우기 버튼 표시용)")
    created_at: datetime


class SourcePageRead(BaseModel):
    """쪽(위치) 하나의 마크다운 본문. 근거 확인용이며 고객 문서라 프로젝트 멤버만 봅니다."""

    id: int = Field(examples=[31])
    seq: int = Field(description="파일 안 순서 (1부터)", examples=[3])
    page_no: int | None = Field(description="진짜 쪽 번호 (PDF 쪽, PPT 슬라이드). 없으면 null", examples=[3])
    location_label: str = Field(examples=["3쪽"])
    text: str

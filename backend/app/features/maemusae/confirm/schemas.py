from datetime import datetime

from pydantic import BaseModel, Field


class ConfirmResult(BaseModel):
    """확정 결과. 내용은 GET …/versions/{version_id} 로 읽습니다."""

    version_id: int = Field(examples=[31])
    revision: int = Field(description="확정 번호. 1 = 첫 확정, 2부터 = 수정 후 확정", examples=[1])
    item_count: int = Field(description="담긴 후보 수 (체크된 것만)", examples=[42])
    confirmed_at: datetime


class ConfirmedDocument(BaseModel):
    """프로젝트 상세 '확정한 문서' 표 한 줄 (확정할 때마다 한 줄씩 쌓임)."""

    version_id: int = Field(examples=[31])
    document_id: int = Field(examples=[1])
    title: str = Field(examples=["요구사항정의서"])
    kind: str = Field(description="공통코드 MMS_DOC_KIND", examples=["REQUIREMENTS"])
    kind_label: str = Field(examples=["요구사항정의서"])
    revision: int = Field(description="1 = 확정, 2부터 = 수정 후 확정", examples=[2])
    item_count: int = Field(examples=[42])
    confirmed_by_name: str = Field(examples=["이소영"])
    confirmed_at: datetime

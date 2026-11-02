from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class VersionEvidence(BaseModel):
    filename: str = Field(examples=["쇼핑몰_요청서.pdf"])
    location_label: str = Field(examples=["3쪽"])
    end_location_label: str | None = Field(default=None, description="쪽을 넘어가는 문장의 끝 쪽", examples=["4쪽"])
    quote: str
    verified: bool


class VersionNote(BaseModel):
    field: Literal["DESCRIPTION", "ANSWER"]
    text: str
    author_name: str = Field(examples=["김다나"])
    updated_at: datetime


class VersionItem(BaseModel):
    """버전에 담긴 후보 하나 (그 순간 그대로, 이후 바뀌지 않음)"""

    code: str = Field(examples=["REQ-015"])
    name: str
    kind: str
    priority: str
    category_major: str | None = None  # 대·중·소분류 (M4-2 전 버전에는 없음)
    category_middle: str | None = None
    category_minor: str | None = None
    description: str
    ai_question: str | None = None
    ai_answer: str | None = None
    is_included: bool
    is_manual: bool
    kind_defaulted: bool = False
    priority_defaulted: bool = False
    sources: list[VersionEvidence] = []
    notes: list[VersionNote] = []


class VersionSaved(BaseModel):
    """버전 추가·버전 저장 결과"""

    id: int
    version_no: int = Field(examples=[2])
    saved_at: datetime = Field(description="화면의 '마지막 버전 v2 (16:32)'")
    overwritten: bool = Field(description="버전 저장이 이번 분석의 마지막 버전을 덮어썼으면 true, 새 버전이면 false")


class VersionListItem(BaseModel):
    id: int
    kind: Literal["SAVED", "CONFIRMED"]
    version_no: int | None = Field(description="SAVED 만 (v1, v2…)", examples=[2])
    revision: int | None = Field(description="CONFIRMED 만 (확정 번호, M4)", examples=[None])
    item_count: int = Field(examples=[42])
    created_by_name: str
    created_at: datetime
    updated_by_name: str | None = Field(default=None, description="버전 저장으로 덮어쓴 사람")
    updated_at: datetime


class VersionDetail(VersionListItem):
    items: list[VersionItem]

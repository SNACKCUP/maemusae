from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

NoteField = Literal["DESCRIPTION", "ANSWER"]


class RequirementListItem(BaseModel):
    """목록 한 줄. 수백 개를 한 번에 그리므로 가벼운 칸만 둡니다 (설명·근거는 상세에서)."""

    id: int = Field(examples=[12])
    code: str = Field(description="문서 안 번호", examples=["REQ-012"])
    name: str = Field(examples=["이메일 회원가입"])
    kind: str = Field(description="공통코드 MMS_REQ_KIND", examples=["FUNCTIONAL"])
    priority: str = Field(description="공통코드 MMS_PRIORITY", examples=["HIGH"])
    category_major: str | None = Field(default=None, description="대분류 (업무 영역). 없으면 null", examples=["회원 관리"])
    category_middle: str | None = Field(default=None, description="중분류", examples=["로그인"])
    category_minor: str | None = Field(default=None, description="소분류", examples=["소셜 로그인"])
    is_included: bool = Field(description="체크. 해제하면 확정에서 빠짐")
    is_manual: bool = Field(description="직접 추가한 후보 (이것만 지울 수 있음)")
    needs_answer: bool = Field(description="AI 질문이 있고 아직 아무도 답을 남기지 않음")
    verified_all: bool = Field(description="근거가 있고 모두 문서에서 확인됨")
    kind_defaulted: bool = Field(description="AI 값이 목록에 없어 구분을 기본값으로 넣음 (확인 필요)")
    priority_defaulted: bool = Field(description="AI 값이 목록에 없어 우선순위를 기본값으로 넣음 (확인 필요)")
    version: int = Field(description="고칠 때 그대로 보냄. 다르면 409 REQUIREMENT_CHANGED", examples=[1])


class RequirementPage(BaseModel):
    items: list[RequirementListItem]
    next_cursor: int | None = Field(default=None, description="다음 페이지를 받을 때 cursor 로 보냄. 없으면 마지막")


class EvidenceRead(BaseModel):
    id: int
    source_file_id: int
    filename: str = Field(description="올린 파일 이름. 직접 쓴 글은 '직접 입력'", examples=["쇼핑몰_요청서.pdf"])
    location_label: str = Field(examples=["3쪽"])
    end_location_label: str | None = Field(default=None, description="문장이 다음 쪽으로 넘어가면 끝 쪽 (화면 3~4쪽)")
    source_page_id: int = Field(description="근거 쪽 본문을 열 때 쓰는 쪽 id")
    quote: str
    verified: bool = Field(description="false 면 화면에 '위치 확인 필요'")


class NoteRead(BaseModel):
    id: int
    requirement_id: int
    requirement_code: str = Field(examples=["REQ-012"])
    requirement_name: str
    field: NoteField
    text: str
    author_name: str = Field(examples=["김다나"])
    mine: bool = Field(description="내가 남긴 입력 (고치기·지우기 버튼)")
    applied: bool = Field(description="다시 분류에 반영됨")
    created_at: datetime
    updated_at: datetime


class RequirementDetail(RequirementListItem):
    description: str
    ai_question: str | None = None
    ai_answer: str | None = None
    sources: list[EvidenceRead]
    notes: list[NoteRead] = Field(description="이 후보에 남긴 입력 (사람마다 칸마다 한 건)")
    created_at: datetime
    updated_at: datetime


def _category(value: str | None) -> str | None:
    """앞뒤·겹친 공백 정리. 빈 글자("")는 그대로 두어 '분류 지우기'로 씀"""
    return " ".join(value.split()) if value is not None else None


CATEGORY_HELP = "업무 영역 (글, 공통코드 아님). 보내지 않으면 그대로, 빈 글자(\"\")면 지움"


class _Changes(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    kind: str | None = Field(default=None, max_length=30)
    priority: str | None = Field(default=None, max_length=30)
    category_major: str | None = Field(default=None, max_length=100, description=f"대분류. {CATEGORY_HELP}")
    category_middle: str | None = Field(default=None, max_length=100, description=f"중분류. {CATEGORY_HELP}")
    category_minor: str | None = Field(default=None, max_length=100, description=f"소분류. {CATEGORY_HELP}")
    is_included: bool | None = None

    @field_validator("category_major", "category_middle", "category_minor")
    @classmethod
    def _clean_category(cls, value: str | None) -> str | None:
        return _category(value)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("이름을 입력하세요.")
        return value.strip() if value else value


class RequirementUpdate(_Changes):
    """보낸 칸만 바꿉니다. 구분·우선순위를 보내면 기본값 표시(*_defaulted)가 풀립니다."""

    version: int = Field(examples=[1])


class RequirementBulkItem(RequirementUpdate):
    id: int


class RequirementBulkUpdate(BaseModel):
    items: list[RequirementBulkItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _unique_ids(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("같은 후보를 두 번 보낼 수 없습니다.")
        return self


class RequirementCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["관리자 통계 화면"])
    description: str = Field(default="", max_length=10_000)
    kind: str = Field(max_length=30, examples=["FUNCTIONAL"])
    priority: str = Field(max_length=30, examples=["MEDIUM"])
    category_major: str | None = Field(default=None, max_length=100, examples=["회원 관리"])
    category_middle: str | None = Field(default=None, max_length=100, examples=["로그인"])
    category_minor: str | None = Field(default=None, max_length=100, examples=[None])

    @field_validator("category_major", "category_middle", "category_minor")
    @classmethod
    def _clean_category(cls, value: str | None) -> str | None:
        return _category(value) or None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("이름을 입력하세요.")
        return value.strip()


class NoteWrite(BaseModel):
    text: str = Field(min_length=1, max_length=5000, examples=["평균 응답 3초 이내로 해 주세요"])

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("내용을 입력하세요.")
        return value.strip()



class CategoryPathRead(BaseModel):
    """이 문서에서 쓰는 분류 하나 (입력 자동완성·대분류 필터용)"""

    major: str = Field(examples=["회원 관리"])
    middle: str | None = Field(default=None, examples=["로그인"])
    minor: str | None = Field(default=None, examples=["소셜 로그인"])
    count: int = Field(description="이 분류의 후보 수", examples=[4])

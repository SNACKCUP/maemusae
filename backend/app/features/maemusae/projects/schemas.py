from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ProjectRole = Literal["ADMIN", "MEMBER"]


class ProjectCreate(BaseModel):
    """프로젝트 만들기. 만든 사람이 관리자가 됩니다."""

    model_config = ConfigDict(extra="forbid")

    name: ProjectName = Field(description="프로젝트명 (앞뒤 공백은 지움)", examples=["쇼핑몰 리뉴얼"])
    start_date: date = Field(examples=["2026-11-01"])
    end_date: date = Field(description="시작일과 같거나 뒤", examples=["2026-12-31"])

    @model_validator(mode="after")
    def _period(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일과 같거나 뒤여야 합니다.")
        return self


class ProjectUpdate(BaseModel):
    """프로젝트 수정 (관리자). 보낸 칸만 바뀝니다."""

    model_config = ConfigDict(extra="forbid")

    name: ProjectName | None = Field(default=None, examples=["쇼핑몰 리뉴얼 2차"])
    start_date: date | None = Field(default=None, examples=["2026-11-01"])
    end_date: date | None = Field(default=None, examples=["2027-01-31"])

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.model_fields_set:
            raise ValueError("바꿀 칸(name, start_date, end_date)을 하나 이상 보내세요.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} 는 비울 수 없습니다.")
        return self


class ProjectRead(BaseModel):
    """프로젝트 하나"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    name: str = Field(examples=["쇼핑몰 리뉴얼"])
    start_date: date = Field(examples=["2026-11-01"])
    end_date: date = Field(examples=["2026-12-31"])
    member_count: int = Field(description="멤버 수", examples=[2])
    my_role: ProjectRole | None = Field(
        description="이 프로젝트에서 내 역할. 멤버가 아닌 서비스 관리자(MASTER)가 보기만 할 때는 null", examples=["ADMIN"]
    )
    created_at: datetime


class ProjectPage(BaseModel):
    """내 프로젝트 목록 한 페이지 (최근 만든 순)"""

    items: list[ProjectRead]
    total: int = Field(description="조건에 맞는 전체 개수", examples=[3])
    page: int = Field(description="지금 페이지 (1부터)", examples=[1])
    size: int = Field(description="페이지당 개수", examples=[20])


class MemberRead(BaseModel):
    """프로젝트 멤버. 이메일은 멤버끼리도 보여 주지 않습니다."""

    id: int = Field(description="멤버 번호 (역할 변경·내보내기 경로에 씀)", examples=[10])
    user_id: str = Field(description="로그인 아이디", examples=["soyoung01"])
    name: str = Field(examples=["이소영"])
    role: ProjectRole = Field(examples=["ADMIN"])
    joined_at: datetime


class MemberRoleUpdate(BaseModel):
    """멤버 역할 변경 (관리자)"""

    model_config = ConfigDict(extra="forbid")

    role: ProjectRole = Field(description="ADMIN(관리자) / MEMBER(일반)", examples=["MEMBER"])

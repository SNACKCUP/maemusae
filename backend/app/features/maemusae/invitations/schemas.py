from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

ProjectRole = Literal["ADMIN", "MEMBER"]
InviteToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class InvitationCreate(BaseModel):
    """초대 보내기 (프로젝트 관리자). 같은 이메일의 이전 초대는 무효가 되고 새 링크가 갑니다."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(description="초대할 이메일 (소문자로 저장)", examples=["dana@example.com"])
    role: ProjectRole = Field(default="MEMBER", description="수락하면 받을 역할. 기본 MEMBER", examples=["MEMBER"])


class InvitationRead(BaseModel):
    """대기 중인 초대 (화면의 "초대 대기" 칩). 프로젝트 관리자만 봅니다."""

    id: int = Field(examples=[3])
    email: str = Field(examples=["dana@example.com"])
    role: ProjectRole = Field(examples=["MEMBER"])
    invited_by_name: str = Field(description="초대한 사람 이름", examples=["이소영"])
    expires_at: datetime
    created_at: datetime


class InvitationTokenBody(BaseModel):
    """초대 링크의 토큰. 주소(경로)에 넣으면 요청 로그에 남으므로 본문으로 받습니다."""

    model_config = ConfigDict(extra="forbid")

    token: InviteToken = Field(description="초대 메일 링크의 token 값", examples=["메일 링크의 token 값"])


class InvitationInfo(BaseModel):
    """초대 링크를 연 사람에게 보여 줄 내용. 화면은 account_exists 로 로그인/가입을 고릅니다."""

    project_name: str = Field(examples=["쇼핑몰 리뉴얼"])
    invited_by_name: str = Field(examples=["이소영"])
    role: ProjectRole = Field(examples=["MEMBER"])
    email: str = Field(description="초대받은 이메일. 가입 화면의 이메일 칸에 고정해서 넣습니다", examples=["dana@example.com"])
    expires_at: datetime
    account_exists: bool = Field(description="이 이메일로 이미 가입했는지. true 면 로그인 후 수락, false 면 가입부터")


class InvitationSignupProof(BaseModel):
    """초대 링크로 가입할 때 쓰는 증표. POST /api/auth/signup 의 email_verification_token 에 넣습니다."""

    email: str = Field(description="가입할 이메일 (초대 이메일로 고정)", examples=["dana@example.com"])
    email_verification_token: str = Field(description="킷 가입 API 에 넣을 1회용 증표")


class InvitationAccepted(BaseModel):
    """초대 수락 결과"""

    project_id: int = Field(examples=[1])
    role: ProjectRole = Field(description="이 프로젝트에서 내 역할", examples=["MEMBER"])

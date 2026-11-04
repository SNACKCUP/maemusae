from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ApiKeyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=300, pattern=r"^sk-\S+$")]


class AiKeyRead(BaseModel):
    """내 AI 키 상태. 키 원문은 돌려주지 않습니다."""

    storage_ready: bool = Field(description="서버에 키 저장 기능이 설정되어 있는지 (false 면 저장 칸을 '준비 중'으로)")
    in_use: bool = Field(description="분석이 개인 키로 도는지 (MMS_USER_AI_KEY_ENABLED). false 면 지금은 서비스 키로 분석")
    provider: Literal["openai"] | None = None
    key_hint: str | None = Field(default=None, description="저장한 키의 끝 4자리", examples=["a1B2"])


class AiKeySave(BaseModel):
    """내 AI 키 저장 (있으면 바꿈)."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai"] = "openai"
    api_key: ApiKeyText = Field(description="OpenAI API 키 (sk- 로 시작). 응답·로그에 남지 않습니다")

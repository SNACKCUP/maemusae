"""개인정보 암호화 설정. crypto 모듈이 직접 읽습니다 (다른 공통 모듈은 이 설정을 모름).

키 두 종류를 따로 둡니다. 둘 다 .env(로컬)와 서버 환경변수(운영)에만 두고 코드·DB·로그에 넣지 않습니다.
- PII_ENCRYPTION_KEYS: 양방향 암호화(AES-256-GCM) 키 목록. "버전:키" 를 쉼표로 이어 씀. 키 교체 때 새 버전을 더함
- PII_HMAC_KEY: 검색용 지문(HMAC-SHA256) 키. 하나만
키 만드는 법: uv run python -m app.crypto.keygen
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings as core_settings

# backend/.env.example 의 로컬 전용 예시 키. 운영에서 이 값 그대로면 시작을 막습니다.
EXAMPLE_PII_ENCRYPTION_KEYS = "1:8xj7zdnU2FUuEoQdOkp2SqAZdG4C7A8_rd4dYMIezY4="
EXAMPLE_PII_HMAC_KEY = "1dFlkkj5UZBEhbXtfBWjhnHLFpitp3dmUmeELEC0PlQ="


class CryptoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pii_encryption_keys: SecretStr = SecretStr("")
    # 새로 암호화할 때 쓸 키 버전. 비우면 목록에서 가장 큰 버전
    pii_encryption_active_key: int | None = None
    pii_hmac_key: SecretStr = SecretStr("")


crypto_settings = CryptoSettings()


def production_problems() -> list[str]:
    """APP_ENV=production 에서 암호화 쪽 위험한 설정. main.py 가 다른 검사와 합쳐 시작 전에 확인합니다.

    회원 개인정보를 저장·검색하는 데 꼭 필요하므로, 저장소·LLM 과 달리 키가 비어 있어도 시작을 막습니다.
    값은 넣지 않고 무엇을 고칠지만 적습니다.
    """
    if core_settings.app_env != "production":
        return []
    from app.crypto.keys import (
        key_problems,  # 순환 import 방지 (keys 가 이 파일을 읽음)
    )

    problems = key_problems(crypto_settings)
    if crypto_settings.pii_encryption_keys.get_secret_value().strip() == EXAMPLE_PII_ENCRYPTION_KEYS:
        problems.append("PII_ENCRYPTION_KEYS: .env.example 의 로컬 전용 예시 키입니다. 새 키를 만드세요")
    if crypto_settings.pii_hmac_key.get_secret_value().strip() == EXAMPLE_PII_HMAC_KEY:
        problems.append("PII_HMAC_KEY: .env.example 의 로컬 전용 예시 키입니다. 새 키를 만드세요")
    return problems

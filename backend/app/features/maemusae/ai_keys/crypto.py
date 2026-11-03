"""키 암호화·풀기 (Fernet = AES-128-CBC + HMAC). 암호화 키는 MMS_AI_KEY_ENCRYPTION_KEY 에서만 읽습니다.

쉼표로 여러 개를 넣으면 맨 앞 것으로 암호화하고, 모두로 풀어 봅니다 (키 교체: 새 키를 앞에 넣고 재저장 후 옛 키 제거).
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.features.maemusae.config import mms_settings


class KeyStorageNotConfiguredError(Exception):
    """암호화 키가 없거나 형식이 틀림"""


class KeyDecryptError(Exception):
    """저장한 키를 풀지 못함 (암호화 키를 바꿨거나 잃어버림)"""


def _parts() -> list[str]:
    return [p.strip() for p in mms_settings.mms_ai_key_encryption_key.get_secret_value().split(",") if p.strip()]


def _fernet() -> MultiFernet:
    parts = _parts()
    if not parts:
        raise KeyStorageNotConfiguredError()
    try:
        return MultiFernet([Fernet(p.encode()) for p in parts])
    except (ValueError, TypeError) as e:
        raise KeyStorageNotConfiguredError() from e


def is_configured() -> bool:
    try:
        _fernet()
    except KeyStorageNotConfiguredError:
        return False
    return True


def key_problem() -> str | None:
    """운영 검사용. 값은 넣지 않고 무엇이 문제인지만"""
    parts = _parts()
    if not parts:
        if mms_settings.mms_user_ai_key_enabled:
            return "MMS_USER_AI_KEY_ENABLED=true 이면 암호화 키가 필요합니다 (만드는 법은 docs 참고)"
        return None
    if not is_configured():
        return "Fernet 키 형식이 아닙니다 (Fernet.generate_key() 로 만든 값)"
    return None


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise KeyDecryptError() from e

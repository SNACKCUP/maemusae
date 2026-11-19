"""암호화 모듈 오류. 메시지와 로그에 키·평문·암호문을 넣지 않습니다."""

from app.core.exceptions import AppError


class CryptoNotConfiguredError(AppError):
    """키가 없거나 형식이 틀림 (설정 문제). 무엇이 틀렸는지는 production_problems·key_problems 로 확인"""

    status_code = 503

    def __init__(self) -> None:
        super().__init__("PII_CRYPTO_NOT_CONFIGURED", "개인정보 암호화 설정이 되어 있지 않습니다. 관리자에게 문의해 주세요.")


class DecryptError(AppError):
    """저장된 암호문을 풀지 못함 (키를 잃었거나, 값이 바뀌었거나, 다른 칸의 값을 옮겨 붙임)"""

    status_code = 500

    def __init__(self) -> None:
        super().__init__("PII_DECRYPT_FAILED", "저장된 정보를 읽지 못했습니다. 관리자에게 문의해 주세요.")


class InvalidPhoneError(AppError):
    """전화번호 형식이 틀림"""

    status_code = 400

    def __init__(self) -> None:
        super().__init__("INVALID_PHONE", "전화번호 형식이 올바르지 않습니다.")

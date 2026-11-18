"""검색용 지문(blind index)과 정규화.

암호문은 매번 달라 WHERE 로 찾을 수 없으므로, 찾아야 하는 값은 "항상 같은 결과가 나오는 지문"을 옆 칸에 둡니다.

    email_hash = HMAC-SHA256(PII_HMAC_KEY, "email:" + normalize_email(값)).hex()

- 그냥 SHA-256 이 아니라 HMAC 이라서, DB 가 새도 키 없이는 흔한 이메일 목록을 해시해 맞춰 볼 수 없습니다.
- 앞에 종류("email:", "phone:")를 붙여, 같은 문자열이라도 종류가 다르면 지문이 다릅니다.
- 저장할 때와 찾을 때 반드시 같은 정규화를 거칩니다. 정확히 같은 값만 찾을 수 있고 부분 검색은 안 됩니다.
"""

import hashlib
import hmac
import re

import phonenumbers

from app.crypto.errors import InvalidPhoneError
from app.crypto.keys import load_keyring

HASH_HEX_LENGTH = 64  # DB 컬럼은 char(64)/varchar(64)
DEFAULT_PHONE_REGION = "KR"
_KIND = re.compile(r"^[a-z][a-z_]*$")


def normalize_email(value: str) -> str:
    """앞뒤 공백 제거 + 소문자. (공급자별 규칙, 예: Gmail 의 점 무시는 넣지 않음)"""
    return value.strip().lower()


def normalize_phone(value: str, region: str = DEFAULT_PHONE_REGION) -> str:
    """국제 표준(E.164) 형식으로. 010-1234-5678, 01012345678, +82 10 1234 5678 → +821012345678

    형식이 틀리면 400 INVALID_PHONE.
    """
    try:
        number = phonenumbers.parse(value.strip(), region)
    except phonenumbers.NumberParseException as e:
        raise InvalidPhoneError() from e
    if not phonenumbers.is_valid_number(number):
        raise InvalidPhoneError()
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def format_phone(e164: str) -> str:
    """화면 표시용. 국내 번호는 010-1234-5678, 해외 번호는 +1 201-555-0123 처럼"""
    number = phonenumbers.parse(e164, None)
    if phonenumbers.region_code_for_number(number) == DEFAULT_PHONE_REGION:
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL)
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


def blind_index(kind: str, normalized: str) -> str:
    """정규화한 값의 지문 (hex 64자). kind 는 소문자 이름 (email, phone 등)"""
    if not _KIND.match(kind):
        raise ValueError("kind 는 소문자 이름이어야 합니다 (예: email)")
    message = f"{kind}:{normalized}".encode()
    return hmac.new(load_keyring().hmac_key, message, hashlib.sha256).hexdigest()


def email_index(value: str) -> str:
    """이메일 지문 (정규화 포함)"""
    return blind_index("email", normalize_email(value))


def phone_index(value: str) -> str:
    """전화번호 지문 (정규화 포함, 형식이 틀리면 400 INVALID_PHONE)"""
    return blind_index("phone", normalize_phone(value))

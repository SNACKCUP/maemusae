"""회원 개인정보 암호화 칸 맞추기 (계획 23 K2: 두 곳에 쓰기).

지금 단계에서는 평문 칸(email, phone, birth_date, postcode, address, address_detail)이 기준이고,
저장할 때마다 같은 행의 암호화 칸(*_enc)과 지문 칸(*_hash), 통계용 birth_year 를 이 함수가 다시 채웁니다.
읽기는 아직 평문 칸에서 합니다. 다음 단계(K3)에서 읽기를 암호화 칸으로 옮기고 평문 쓰기를 멈춥니다.

models.py 의 before_insert/before_update 이벤트가 부르므로, 가입·내 정보 수정·시드·소셜 가입·익명화 등
어느 경로로 저장해도 빠지지 않습니다 (JPA 의 @PrePersist/@PreUpdate 와 같은 자리).
"""

from datetime import date
from typing import Any

from app.crypto import (
    InvalidPhoneError,
    email_index,
    normalize_email,
    normalize_phone,
    phone_index,
)
from app.crypto.keys import load_keyring

# 평문 칸 → 함께 바뀌는 칸. 이 칸 중 하나라도 바뀌면 그 행의 암호화 칸을 모두 다시 씀 (키 버전이 행 안에서 섞이지 않게)
PLAIN_PII_FIELDS = ("email", "phone", "birth_date", "postcode", "address", "address_detail")


def phone_for_storage(phone: str) -> tuple[str, str | None]:
    """(암호화 칸에 넣을 값, 지문). 형식이 맞으면 E.164 와 지문, 틀린 옛 데이터는 원래 값 그대로와 지문 없음"""
    try:
        return normalize_phone(phone), phone_index(phone)
    except InvalidPhoneError:
        return phone.strip(), None


def sync_encrypted_fields(user: Any) -> None:
    """평문 칸 값으로 암호화·지문·birth_year 칸을 채웁니다. 값 자체는 로그에 남기지 않습니다."""
    user.email_enc = normalize_email(user.email) if user.email is not None else None
    user.email_hash = email_index(user.email) if user.email is not None else None
    if user.phone:
        user.phone_enc, user.phone_hash = phone_for_storage(user.phone)
    else:
        user.phone_enc = user.phone_hash = None
        user.phone_verified_at = None
    birth_date = user.birth_date
    if isinstance(birth_date, str):  # 일부 경로는 저장 직전까지 "YYYY-MM-DD" 문자열로 들고 있음 (DB 가 날짜로 바꿈)
        birth_date = date.fromisoformat(birth_date)
    user.birth_date_enc = birth_date
    user.birth_year = birth_date.year if birth_date is not None else None
    user.postcode_enc = user.postcode
    user.address_enc = user.address
    user.address_detail_enc = user.address_detail
    user.pii_key_version = load_keyring().active_version


def needs_sync(user: Any, changed: set[str]) -> bool:
    """평문 칸이 바뀌었거나, 아직 한 번도 채우지 않은 행인지"""
    return user.pii_key_version is None or bool(changed & set(PLAIN_PII_FIELDS))

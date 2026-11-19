"""회원 개인정보 암호화 칸 맞추기 (계획 23).

이제 `user.email`·`phone`·`birth_date`·`postcode`·`address`·`address_detail` 은 암호화 칸(*_enc)입니다
(models.py 에서 속성 이름은 그대로 두고 DB 칸만 바꿈). 저장할 때 이 함수가
- 이메일은 소문자로 맞추고 지문(email_hash)을,
- 전화번호는 E.164(+821012345678)로 바꾸고 지문(phone_hash)을, 번호가 바뀌면 phone_verified_at 을 지우고,
- 생년월일에서 통계용 birth_year 를,
- 한 칸이라도 바뀌면 그 행의 암호화 칸을 모두 지금 키로 다시 암호화하고 pii_key_version 을
채웁니다. 평문 칸은 없습니다 (K4 에서 삭제).

models.py 의 before_insert/before_update 이벤트가 부르므로, 어느 경로로 저장해도 빠지지 않습니다
(JPA 의 @PrePersist/@PreUpdate 와 같은 자리). 값 자체는 로그에 남기지 않습니다.
"""

from datetime import date
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.crypto import (
    InvalidPhoneError,
    email_index,
    format_phone,
    normalize_email,
    normalize_phone,
    phone_index,
)
from app.crypto.keys import load_keyring

# 암호화해 저장하는 칸 (속성 이름). 하나라도 바뀌면 모두 다시 암호화 (키 버전이 행 안에서 섞이지 않게)
PII_FIELDS = ("email", "phone", "birth_date", "postcode", "address", "address_detail")


def phone_for_storage(phone: str) -> tuple[str, str | None]:
    """(암호화 칸에 넣을 값, 지문). 형식이 맞으면 E.164 와 지문, 틀린 옛 데이터는 원래 값 그대로와 지문 없음"""
    try:
        return normalize_phone(phone), phone_index(phone)
    except InvalidPhoneError:
        return phone.strip(), None


def check_phone(phone: str | None) -> None:
    """새로 받는 전화번호 검사 (가입·내 정보 수정). 틀리면 400 INVALID_PHONE"""
    if phone:
        normalize_phone(phone)


def display_phone(stored: str | None) -> str | None:
    """응답에 보여 줄 모양: 한국 번호는 010-1234-5678, 그 밖은 국제 형식. 형식이 틀린 옛 값은 그대로"""
    if not stored:
        return stored
    try:
        return format_phone(stored)
    except Exception:  # noqa: BLE001 - 옛 데이터는 저장된 그대로 보여 줌
        return stored


def mask_email(email: str) -> str:
    """관리자 목록용 가린 이메일: kim.minji@example.com → ki*******@example.com (계획 23 D7)"""
    local, sep, domain = email.partition("@")
    if not sep:
        return "***"
    keep = local[:2] if len(local) > 2 else local[:1]
    return f"{keep}{'*' * max(len(local) - len(keep), 1)}@{domain}"


def mask_phone(display: str | None) -> str | None:
    """관리자 목록용 가린 전화번호: 010-1234-5678 → 010-****-5678. 마지막 4자리와 앞 묶음만 남김"""
    if not display:
        return display
    digits = [i for i, ch in enumerate(display) if ch.isdigit()]
    if len(digits) <= 4:
        return "*" * len(display)
    first_group = display.split("-")[0] if "-" in display else display[:3]
    keep = set(range(len(first_group))) | set(digits[-4:])
    return "".join(ch if (i in keep or not ch.isdigit()) else "*" for i, ch in enumerate(display))


def mask_place(value: str | None, *, keep_words: int = 0, keep_chars: int = 0) -> str | None:
    """관리자 목록용 가린 주소·우편번호. 주소는 앞 단어만(서울 강남구 ***), 우편번호는 앞 글자만(06***)"""
    if not value:
        return value
    if keep_words:
        words = value.split()
        if len(words) > keep_words:
            return " ".join(words[:keep_words]) + " ***"
        return "***"
    if keep_chars:
        return value[:keep_chars] + "*" * max(len(value) - keep_chars, 1)
    return "***"


def _as_date(value: Any) -> date | None:
    if isinstance(value, str):  # 일부 경로는 저장 직전까지 "YYYY-MM-DD" 문자열로 들고 있음
        return date.fromisoformat(value)
    return value


def sync_on_write(user: Any, changed: set[str]) -> None:
    """저장 직전에 부름. changed = 이번에 바뀐 PII 칸 (새 행이면 전부)."""
    if "email" in changed:
        if user.email is not None:
            user.email = normalize_email(user.email)
        user.email_hash = email_index(user.email) if user.email is not None else None
    if "phone" in changed:
        raw = user.phone.strip() if user.phone else None
        old_hash = user.phone_hash
        if raw:
            user.phone, user.phone_hash = phone_for_storage(raw)
        else:
            user.phone = user.phone_hash = None
        if user.phone_hash is None or user.phone_hash != old_hash:
            user.phone_verified_at = None  # 번호가 바뀌면 인증(향후 SMS)을 다시 받아야 함 (모양만 다르면 그대로)
    if "birth_date" in changed:
        user.birth_date = _as_date(user.birth_date)
        user.birth_year = user.birth_date.year if user.birth_date is not None else None
    # 바뀌지 않은 칸도 지금 키로 다시 암호화되도록 표시 (값은 같고 암호문만 새로 만듦)
    for field in PII_FIELDS:
        if field not in changed:
            getattr(user, field)  # 만료된 칸이면 먼저 읽어 둠 (flag_modified 는 읽힌 칸에만 됨)
            flag_modified(user, field)
    user.pii_key_version = load_keyring().active_version

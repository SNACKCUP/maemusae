"""개인정보 암호화 모듈 (app.crypto): 암호화·복호화, 키 버전, 지문, 정규화, 컬럼 타입, 운영 설정 검사"""

import base64
import logging
from datetime import date

import pytest
from pydantic import SecretStr
from sqlalchemy import Column, Integer, MetaData, Table, insert, select, text

from app.core.config import settings
from app.crypto import (
    CryptoNotConfiguredError,
    DecryptError,
    EncryptedDate,
    EncryptedString,
    InvalidPhoneError,
    blind_index,
    decrypt,
    email_index,
    encrypt,
    format_phone,
    key_version,
    needs_reencrypt,
    normalize_email,
    normalize_phone,
    phone_index,
    reencrypt,
)
from app.crypto import config as crypto_config
from app.crypto.config import (
    EXAMPLE_PII_ENCRYPTION_KEYS,
    EXAMPLE_PII_HMAC_KEY,
    CryptoSettings,
    crypto_settings,
)
from app.crypto.keys import key_problems
from app.main import check_startup


def _key(fill: int) -> str:
    return base64.urlsafe_b64encode(bytes([fill]) * 32).decode()


KEY1, KEY2, HMAC_KEY = _key(1), _key(2), _key(9)


def _use_keys(monkeypatch, keys: str, hmac_key: str = HMAC_KEY, active: int | None = None) -> None:
    monkeypatch.setattr(crypto_settings, "pii_encryption_keys", SecretStr(keys))
    monkeypatch.setattr(crypto_settings, "pii_hmac_key", SecretStr(hmac_key))
    monkeypatch.setattr(crypto_settings, "pii_encryption_active_key", active)


@pytest.fixture(autouse=True)
def test_keys(monkeypatch):
    """테스트는 개발자 .env 와 상관없이 정해진 키로 돕니다 (CI 에는 키가 없음)"""
    _use_keys(monkeypatch, f"1:{KEY1}")


# ---- 암호화·복호화 ----


def test_roundtrip_and_random_nonce():
    a = encrypt("010-1234-5678", "users.phone")
    b = encrypt("010-1234-5678", "users.phone")
    assert a != b  # 같은 값도 매번 다른 암호문
    assert decrypt(a, "users.phone") == decrypt(b, "users.phone") == "010-1234-5678"
    assert b"010" not in a
    assert len(a) == len(b"010-1234-5678") + 29


def test_korean_text_roundtrip():
    assert decrypt(encrypt("서울 강남구 테헤란로 123", "users.address"), "users.address") == "서울 강남구 테헤란로 123"


def test_tampered_ciphertext_fails():
    blob = bytearray(encrypt("kim@example.com", "users.email"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptError):
        decrypt(bytes(blob), "users.email")


def test_other_column_aad_fails():
    """다른 칸의 암호문을 옮겨 붙이면 풀리지 않음"""
    blob = encrypt("010-1234-5678", "users.phone")
    with pytest.raises(DecryptError):
        decrypt(blob, "users.email")


def test_too_short_blob_fails():
    with pytest.raises(DecryptError):
        decrypt(b"\x01abc", "users.email")


def test_decrypt_failure_log_has_no_value(caplog):
    """로그에는 aad·키 버전·이유만. 평문·암호문은 남기지 않음 (app 로거는 propagate=False 라 잠시 켬)"""
    app_logger = logging.getLogger("app")
    old = app_logger.propagate
    app_logger.propagate = True
    try:
        blob = encrypt("secret-value@example.com", "users.email")
        with caplog.at_level(logging.ERROR, logger="app.crypto"), pytest.raises(DecryptError):
            decrypt(blob, "users.phone")
    finally:
        app_logger.propagate = old
    assert "invalid_tag" in caplog.text
    assert "secret-value" not in caplog.text


def test_memoryview_from_db_driver():
    blob = encrypt("x", "t.c")
    assert decrypt(memoryview(blob), "t.c") == "x"


# ---- 키 버전·교체 ----


def test_old_key_still_decrypts_after_rotation(monkeypatch):
    old = encrypt("kim@example.com", "users.email")
    assert key_version(old) == 1
    _use_keys(monkeypatch, f"1:{KEY1},2:{KEY2}")  # 새 버전 추가 → 가장 큰 버전이 활성
    assert decrypt(old, "users.email") == "kim@example.com"
    new = encrypt("kim@example.com", "users.email")
    assert key_version(new) == 2
    assert needs_reencrypt(old) and not needs_reencrypt(new)
    rotated = reencrypt(old, "users.email")
    assert key_version(rotated) == 2 and decrypt(rotated, "users.email") == "kim@example.com"
    assert reencrypt(new, "users.email") == new  # 이미 활성 키면 그대로


def test_active_key_can_be_pinned(monkeypatch):
    _use_keys(monkeypatch, f"1:{KEY1},2:{KEY2}", active=1)
    assert key_version(encrypt("a", "t.c")) == 1


def test_removed_key_cannot_decrypt(monkeypatch):
    blob = encrypt("a", "t.c")
    _use_keys(monkeypatch, f"2:{KEY2}")
    with pytest.raises(DecryptError):
        decrypt(blob, "t.c")


@pytest.mark.parametrize(
    ("keys", "hmac_key", "active", "name"),
    [
        ("", HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),
        (KEY1, HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),  # 버전 없음
        ("0:" + KEY1, HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),
        ("1:" + KEY1 + ",1:" + KEY2, HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),  # 같은 버전 두 번
        ("1:" + base64.urlsafe_b64encode(b"short").decode(), HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),
        ("1:not base64!!", HMAC_KEY, None, "PII_ENCRYPTION_KEYS"),
        ("1:" + KEY1, "", None, "PII_HMAC_KEY"),
        ("1:" + KEY1, base64.urlsafe_b64encode(b"x" * 16).decode(), None, "PII_HMAC_KEY"),
        ("1:" + KEY1, KEY1, None, "PII_HMAC_KEY"),  # 암호화 키와 같음
        ("1:" + KEY1, HMAC_KEY, 3, "PII_ENCRYPTION_ACTIVE_KEY"),
    ],
)
def test_bad_key_settings(monkeypatch, keys, hmac_key, active, name):
    _use_keys(monkeypatch, keys, hmac_key, active)
    problems = key_problems(crypto_settings)
    assert len(problems) == 1 and problems[0].startswith(name)
    assert KEY1 not in problems[0] and KEY2 not in problems[0]  # 문구에 키 값을 넣지 않음
    with pytest.raises(CryptoNotConfiguredError):
        encrypt("a", "t.c")


def test_not_configured_is_503(monkeypatch):
    _use_keys(monkeypatch, "", "")
    with pytest.raises(CryptoNotConfiguredError) as e:
        email_index("a@b.com")
    assert e.value.status_code == 503 and e.value.code == "PII_CRYPTO_NOT_CONFIGURED"


def test_example_keys_from_env_example_are_valid():
    """.env.example 의 예시 키로 로컬에서 바로 동작해야 함"""
    s = CryptoSettings(
        _env_file=None,
        pii_encryption_keys=SecretStr(EXAMPLE_PII_ENCRYPTION_KEYS),
        pii_hmac_key=SecretStr(EXAMPLE_PII_HMAC_KEY),
    )
    assert key_problems(s) == []


# ---- 지문·정규화 ----


def test_email_index_ignores_case_and_spaces():
    assert normalize_email("  Kim@Example.COM ") == "kim@example.com"
    assert email_index(" Kim@Example.COM") == email_index("kim@example.com")
    assert email_index("kim@example.com") != email_index("lee@example.com")
    assert len(email_index("kim@example.com")) == 64


def test_index_depends_on_kind_and_key(monkeypatch):
    assert blind_index("email", "x") != blind_index("phone", "x")
    before = email_index("kim@example.com")
    _use_keys(monkeypatch, f"1:{KEY1}", hmac_key=_key(8))
    assert email_index("kim@example.com") != before  # 키가 없으면 맞춰 볼 수 없음


def test_index_kind_must_be_a_name():
    with pytest.raises(ValueError):
        blind_index("Email:", "x")


@pytest.mark.parametrize("raw", ["010-1234-5678", "01012345678", "010 1234 5678", "+82 10-1234-5678", "+821012345678"])
def test_phone_normalized_to_e164(raw):
    assert normalize_phone(raw) == "+821012345678"
    assert phone_index(raw) == phone_index("01012345678")


def test_phone_formats():
    assert normalize_phone("02-123-4567") == "+8221234567"
    assert format_phone("+821012345678") == "010-1234-5678"
    assert format_phone(normalize_phone("+1 201-555-0123")) == "+1 201-555-0123"


@pytest.mark.parametrize("raw", ["", "abc", "010-12", "123456789012345678"])
def test_invalid_phone(raw):
    with pytest.raises(InvalidPhoneError) as e:
        normalize_phone(raw)
    assert e.value.code == "INVALID_PHONE" and e.value.status_code == 400


# ---- 컬럼 타입 (실제 PostgreSQL) ----

_meta = MetaData()
_people = Table(
    "tmp_crypto_people",
    _meta,
    Column("id", Integer, primary_key=True),
    Column("phone_enc", EncryptedString("tmp.phone")),
    Column("birth_date_enc", EncryptedDate("tmp.birth_date")),
    prefixes=["TEMPORARY"],
)


def test_encrypted_columns_store_ciphertext(db):
    conn = db.connection()
    _people.create(conn)
    conn.execute(insert(_people), [
        {"id": 1, "phone_enc": "+821012345678", "birth_date_enc": date(1995, 4, 12)},
        {"id": 2, "phone_enc": None, "birth_date_enc": None},
    ])
    rows = conn.execute(select(_people).order_by(_people.c.id)).all()
    assert rows[0].phone_enc == "+821012345678" and rows[0].birth_date_enc == date(1995, 4, 12)
    assert rows[1].phone_enc is None and rows[1].birth_date_enc is None
    raw = conn.execute(text("SELECT phone_enc, birth_date_enc, pg_typeof(phone_enc)::text FROM tmp_crypto_people WHERE id = 1")).one()
    assert raw[2] == "bytea"
    assert b"1012345678" not in bytes(raw[0]) and b"1995" not in bytes(raw[1])  # DB 에는 평문이 없음


# ---- 운영 설정 검사 ----


def test_production_requires_keys(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _use_keys(monkeypatch, "", "")
    assert any(p.startswith("PII_ENCRYPTION_KEYS") for p in crypto_config.production_problems())


def test_production_rejects_example_keys(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _use_keys(monkeypatch, EXAMPLE_PII_ENCRYPTION_KEYS, EXAMPLE_PII_HMAC_KEY)
    problems = crypto_config.production_problems()
    assert any("PII_ENCRYPTION_KEYS" in p for p in problems) and any("PII_HMAC_KEY" in p for p in problems)


def test_production_accepts_real_keys(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    assert crypto_config.production_problems() == []


def test_local_is_never_checked(monkeypatch):
    _use_keys(monkeypatch, "", "")
    assert crypto_config.production_problems() == []


def test_startup_check_includes_crypto(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    _use_keys(monkeypatch, "", "")
    with pytest.raises(RuntimeError, match="PII_ENCRYPTION_KEYS"):
        check_startup()

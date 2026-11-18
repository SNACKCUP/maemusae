"""개인정보 암호화 칸 두 곳에 쓰기와 기존 행 채우기 (계획 23 K2)"""

from datetime import UTC, date, datetime

from sqlalchemy import text

from app.auth.models import EmailVerification
from app.crypto import decrypt, email_index, phone_index
from app.social import pii_backfill as social_backfill
from app.social.models import SocialAccount
from app.users import pii_backfill, service

PROFILE = {
    "phone": "010-1234-5678",
    "postcode": "06236",
    "address": "서울 강남구 테헤란로 123",
    "address_detail": "4층 401호",
    "birth_date": date(1995, 4, 12),
    "gender": "female",
}


def _user(db, login_id="kimpii", email="Kim.Pii@Example.com", profile=None):
    return service.create_user(
        db, login_id=login_id, email=email, password="Password1!", name="김개인", profile=profile or PROFILE
    )


def _raw(db, user_id):
    return db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).mappings().one()


def test_signup_fills_encrypted_columns(db):
    user = _user(db)
    row = _raw(db, user.id)
    assert row["email"] == "kim.pii@example.com"  # 평문 칸은 그대로 (K2: 읽기는 아직 평문)
    assert row["email_hash"] == email_index("kim.pii@example.com")
    assert decrypt(row["email_enc"], "users.email") == "kim.pii@example.com"
    assert decrypt(row["phone_enc"], "users.phone") == "+821012345678"
    assert row["phone_hash"] == phone_index("01012345678")
    assert decrypt(row["birth_date_enc"], "users.birth_date") == "1995-04-12"
    assert row["birth_year"] == 1995
    assert decrypt(row["postcode_enc"], "users.postcode") == "06236"
    assert decrypt(row["address_enc"], "users.address") == "서울 강남구 테헤란로 123"
    assert decrypt(row["address_detail_enc"], "users.address_detail") == "4층 401호"
    assert row["gender"] == "female"  # 성별은 통계용 평문 (D5)
    assert row["pii_key_version"] == 1
    for col in ("email_enc", "phone_enc", "address_enc"):
        assert b"example" not in bytes(row[col]) and "강남".encode() not in bytes(row[col])
    # 모델로 읽으면 평문으로 풀림
    assert user.email_enc == "kim.pii@example.com" and user.birth_date_enc == date(1995, 4, 12)


def test_user_without_optional_fields(db):
    user = service.create_user(db, login_id="plainuser", email="plain@example.com", password="Password1!", name="평범")
    row = _raw(db, user.id)
    assert row["email_hash"] == email_index("plain@example.com")
    assert row["phone_enc"] is None and row["phone_hash"] is None and row["birth_year"] is None
    assert row["pii_key_version"] == 1


def test_profile_change_rewrites_encrypted_columns(db):
    user = _user(db)
    before = _raw(db, user.id)
    service.update_profile(db, user, {"phone": "010 9999 8888", "birth_date": None})
    after = _raw(db, user.id)
    assert decrypt(after["phone_enc"], "users.phone") == "+821099998888"
    assert after["phone_hash"] == phone_index("01099998888")
    assert after["birth_date_enc"] is None and after["birth_year"] is None
    assert after["email_hash"] == before["email_hash"]


def test_email_change_updates_hash(db):
    user = _user(db)
    service.update_profile(db, user, {"email": "New@Example.com"})
    row = _raw(db, user.id)
    assert row["email_hash"] == email_index("new@example.com")
    assert decrypt(row["email_enc"], "users.email") == "new@example.com"


def test_unrelated_update_keeps_ciphertext(db):
    """로그인 시각처럼 개인정보가 아닌 칸만 바뀌면 암호문을 다시 쓰지 않음"""
    user = _user(db)
    before = _raw(db, user.id)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    after = _raw(db, user.id)
    assert bytes(after["phone_enc"]) == bytes(before["phone_enc"])


def test_invalid_legacy_phone_gets_no_hash(db):
    user = _user(db, profile={"phone": "12-34"})
    row = _raw(db, user.id)
    assert decrypt(row["phone_enc"], "users.phone") == "12-34"
    assert row["phone_hash"] is None


def test_anonymize_clears_encrypted_columns(db):
    user = _user(db)
    service.anonymize(user)
    db.commit()
    row = _raw(db, user.id)
    assert row["phone_enc"] is None and row["phone_hash"] is None and row["address_enc"] is None
    assert row["birth_year"] is None
    assert row["email_hash"] == email_index(row["email"])  # 자리표시 이메일도 지문이 있음 (K3 NOT NULL 대비)


def _make_legacy(db, user_id):
    """K2 전에 저장된 행처럼 암호화 칸을 비움"""
    db.execute(
        text(
            "UPDATE users SET email_enc=NULL, email_hash=NULL, phone_enc=NULL, phone_hash=NULL, birth_date_enc=NULL,"
            " birth_year=NULL, postcode_enc=NULL, address_enc=NULL, address_detail_enc=NULL, pii_key_version=NULL"
            " WHERE id = :id"
        ),
        {"id": user_id},
    )
    db.expire_all()


def test_backfill_fills_legacy_rows_and_is_rerunnable(db):
    a = _user(db)
    b = _user(db, login_id="leepii", email="lee@example.com", profile={"phone": "bad"})
    _make_legacy(db, a.id)
    _make_legacy(db, b.id)
    assert pii_backfill.backfill(db, dry_run=True) == 2
    assert pii_backfill.backfill(db, batch_size=1) == 2  # 배치를 나눠도 모두 처리
    assert pii_backfill.backfill(db) == 0  # 다시 돌려도 할 일 없음
    row = _raw(db, a.id)
    assert row["email_hash"] == email_index("kim.pii@example.com") and row["birth_year"] == 1995
    assert decrypt(row["phone_enc"], "users.phone") == "+821012345678"
    assert _raw(db, b.id)["phone_hash"] is None
    from app.users import repository

    assert repository.count_pii_unsynced(db) == 0
    assert repository.count_phone_without_hash(db) >= 1


def test_backfill_main_logs_counts_only(db, monkeypatch, caplog):
    import logging

    from app.users import pii_backfill as module

    class _Ctx:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(module, "SessionLocal", lambda: _Ctx())
    user = _user(db)
    _make_legacy(db, user.id)
    app_logger = logging.getLogger("app")
    old = app_logger.propagate
    app_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="app.users.pii_backfill"):
            assert module.main([]) == 0
    finally:
        app_logger.propagate = old
    assert "남은 행 0건" in caplog.text
    assert "kim.pii" not in caplog.text and "1234" not in caplog.text


def test_email_verification_gets_hash(db):
    now = datetime.now(UTC)
    row = EmailVerification(email="code@example.com", code_hash="x" * 64, expires_at=now, created_at=now)
    db.add(row)
    db.commit()
    assert row.email_hash == email_index("code@example.com")


def test_social_account_email_encrypted_and_backfilled(db):
    user = _user(db)
    account = SocialAccount(user_id=user.id, provider="google", provider_user_id="sub-1", email="g@example.com")
    db.add(account)
    db.commit()
    raw = db.execute(text("SELECT email_enc FROM social_accounts WHERE id = :id"), {"id": account.id}).scalar_one()
    assert decrypt(raw, "social_accounts.email") == "g@example.com"
    account.email = "g2@example.com"
    db.commit()
    raw = db.execute(text("SELECT email_enc FROM social_accounts WHERE id = :id"), {"id": account.id}).scalar_one()
    assert decrypt(raw, "social_accounts.email") == "g2@example.com"
    db.execute(text("UPDATE social_accounts SET email_enc = NULL WHERE id = :id"), {"id": account.id})
    db.expire_all()
    assert social_backfill.backfill(db, dry_run=True) == 1
    assert social_backfill.backfill(db) == 1
    assert social_backfill.backfill(db) == 0

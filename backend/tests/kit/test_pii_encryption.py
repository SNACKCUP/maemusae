"""개인정보 암호화 칸으로 읽기·찾기 (계획 23 K3)

모델의 email·phone·birth_date·postcode·address·address_detail 은 암호화 칸(*_enc)이고, 찾기는 지문 칸으로 합니다.
옛 평문 칸은 K4 에서 지웠습니다 (테이블에 평문 개인정보 칸이 없음).
"""

import logging
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, text

from app.auth.models import EmailVerification
from app.core.logging import PiiRedactFilter, redact_pii
from app.crypto import InvalidPhoneError, decrypt, email_index, phone_index
from app.social.models import SocialAccount
from app.users import pii, repository, service
from app.users.models import User
from app.users.service import UserError

PROFILE = {
    "phone": "010-1234-5678",
    "postcode": "06236",
    "address": "서울 강남구 테헤란로 123",
    "address_detail": "4층 401호",
    "birth_date": date(1995, 4, 12),
    "gender": "female",
}


def _user(db, login_id="kimpii", email="Kim.Pii@Example.com", profile=None, name="김개인"):
    return service.create_user(
        db, login_id=login_id, email=email, password="Password1!", name=name, profile=profile or PROFILE
    )


def _cols(db, table):
    return set(
        db.scalars(text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"), {"t": table})
    )


def _raw(db, user_id):
    return db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).mappings().one()


# ---- 저장 ----


def test_signup_stores_ciphertext_and_reads_plaintext(db):
    user = _user(db)
    row = _raw(db, user.id)
    assert decrypt(row["email_enc"], "users.email") == "kim.pii@example.com"
    assert row["email_hash"] == email_index("kim.pii@example.com")
    assert decrypt(row["phone_enc"], "users.phone") == "+821012345678"
    assert row["phone_hash"] == phone_index("01012345678")
    assert decrypt(row["birth_date_enc"], "users.birth_date") == "1995-04-12"
    assert row["birth_year"] == 1995
    assert decrypt(row["postcode_enc"], "users.postcode") == "06236"
    assert decrypt(row["address_enc"], "users.address") == "서울 강남구 테헤란로 123"
    assert decrypt(row["address_detail_enc"], "users.address_detail") == "4층 401호"
    assert row["gender"] == "female"  # 성별은 통계용 평문 (D5)
    assert row["pii_key_version"] == 1
    for col in ("email_enc", "phone_enc", "address_enc", "postcode_enc"):
        raw = bytes(row[col])
        assert b"example" not in raw and "강남".encode() not in raw and b"06236" not in raw
    # 평문 개인정보 칸은 남아 있지 않음 (K4)
    for col in ("email", "phone", "postcode", "address", "address_detail", "birth_date"):
        assert col not in row
    # 모델로 읽으면 평문
    db.expire_all()
    again = db.get(User, user.id)
    assert again.email == "kim.pii@example.com" and again.phone == "+821012345678"
    assert again.birth_date == date(1995, 4, 12) and again.address_detail == "4층 401호"


def test_email_lookup_ignores_case_and_duplicate_is_blocked(db):
    user = _user(db)
    assert repository.get_by_email(db, " KIM.PII@example.COM ").id == user.id
    with pytest.raises(UserError) as e:
        _user(db, login_id="other01", email="kim.pii@EXAMPLE.com")
    assert e.value.code == "EMAIL_TAKEN"


def test_encrypted_columns_cannot_be_used_in_where(db):
    with pytest.raises(TypeError):
        select(User).where(User.email == "kim.pii@example.com")
    with pytest.raises(TypeError):
        select(User).where(User.phone.ilike("%010%"))
    select(User).where(User.phone.is_(None), User.email.is_not(None))  # NULL 확인은 됨


def test_invalid_phone_is_rejected(db):
    with pytest.raises(InvalidPhoneError):
        _user(db, profile={"phone": "12-34"})
    user = _user(db, profile={"phone": "01012345678"})
    with pytest.raises(InvalidPhoneError):
        service.update_profile(db, user, {"phone": "abc"})


def test_profile_change_re_encrypts_whole_row(db):
    user = _user(db)
    before = _raw(db, user.id)
    service.update_profile(db, user, {"address": "부산 해운대구 1", "birth_date": None})
    after = _raw(db, user.id)
    assert decrypt(after["address_enc"], "users.address") == "부산 해운대구 1"
    assert after["birth_date_enc"] is None and after["birth_year"] is None
    # 바뀌지 않은 칸도 새 암호문 (키 버전이 행 안에서 섞이지 않게), 값과 지문은 같음
    assert bytes(after["email_enc"]) != bytes(before["email_enc"])
    assert decrypt(after["email_enc"], "users.email") == "kim.pii@example.com"
    assert after["email_hash"] == before["email_hash"] and after["phone_hash"] == before["phone_hash"]


def test_phone_change_updates_hash_and_clears_verification(db):
    user = _user(db)
    user.phone_verified_at = datetime.now(UTC)
    db.commit()
    service.update_profile(db, user, {"phone": "+82 10 1234 5678"})  # 같은 번호를 다른 모양으로
    assert _raw(db, user.id)["phone_verified_at"] is not None
    service.update_profile(db, user, {"phone": "010 9999 8888"})
    row = _raw(db, user.id)
    assert decrypt(row["phone_enc"], "users.phone") == "+821099998888"
    assert row["phone_hash"] == phone_index("01099998888") and row["phone_verified_at"] is None


def test_unrelated_update_keeps_ciphertext(db):
    """로그인 시각처럼 개인정보가 아닌 칸만 바뀌면 암호문을 다시 쓰지 않음"""
    user = _user(db)
    before = _raw(db, user.id)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    assert bytes(_raw(db, user.id)["phone_enc"]) == bytes(before["phone_enc"])


def test_anonymize_clears_encrypted_columns(db):
    user = _user(db)
    service.anonymize(user)
    db.commit()
    row = _raw(db, user.id)
    assert row["phone_enc"] is None and row["phone_hash"] is None and row["address_enc"] is None
    assert row["birth_year"] is None
    placeholder = decrypt(row["email_enc"], "users.email")
    assert placeholder.endswith("@deleted.invalid") and row["email_hash"] == email_index(placeholder)


# ---- 화면에 보이는 모양 ----


def test_display_helpers():
    assert pii.display_phone("+821012345678") == "010-1234-5678"
    assert pii.display_phone("12-34") == "12-34"  # 형식이 틀린 옛 값은 그대로
    assert pii.display_phone(None) is None
    assert pii.mask_email("kim.minji@example.com") == "ki*******@example.com"
    assert pii.mask_email("ab@example.com") == "a*@example.com"
    assert pii.mask_email("a@example.com") == "a*@example.com"


def test_me_shows_phone_in_local_format(client, make_user, login):
    make_user("user01", phone="+82 10 1234 5678")
    headers = login("user01")
    assert client.get("/api/users/me", headers=headers).json()["phone"] == "010-1234-5678"
    bad = client.patch("/api/users/me", headers=headers, json={"phone": "123"})
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_PHONE"


# ---- 관리자 ----


def test_admin_list_masks_email_and_detail_shows_full(client, make_user, login):
    make_user("admin01", admin=True)
    target = make_user("member01", email="member.one@example.com", name="회원하나")
    headers = login("admin01")
    page = client.get("/api/users", headers=headers, params={"q": "member"}).json()
    [item] = page["items"]
    assert item["email"] == "me********@example.com"
    detail = client.get(f"/api/users/{target.id}", headers=headers)
    assert detail.status_code == 200 and detail.json()["email"] == "member.one@example.com"
    assert client.get("/api/users/999999", headers=headers).status_code == 404


def test_admin_search_by_exact_email_only(client, make_user, login):
    make_user("admin01", admin=True)
    make_user("member01", email="member.one@example.com", name="회원하나")
    headers = login("admin01")

    def ids(q):
        return [u["user_id"] for u in client.get("/api/users", headers=headers, params={"q": q}).json()["items"]]

    assert ids("Member.One@Example.com") == ["member01"]  # 전체 주소는 대소문자 무시하고 정확히
    assert ids("member.one@example") == []  # 일부만으로는 못 찾음
    assert ids("회원") == ["member01"]  # 이름·아이디·닉네임은 그대로 포함 검색


def test_admin_detail_requires_admin(client, make_user, login):
    target = make_user("member01")
    make_user("member02")
    assert client.get(f"/api/users/{target.id}", headers=login("member02")).status_code == 403


# ---- 전화번호로 아이디 찾기 (계획 23 §8-2) ----

PHONE_URL = "/api/auth/id/forgot-by-phone"


def test_find_id_by_phone_mails_registered_email(client, make_user, mail_outbox):
    make_user("user01", name="홍길동", phone="010-1234-5678")
    ok = client.post(PHONE_URL, json={"name": "홍길동", "phone": "+82 10-1234-5678"})
    wrong_name = client.post(PHONE_URL, json={"name": "김철수", "phone": "010-1234-5678"})
    unknown = client.post(PHONE_URL, json={"name": "홍길동", "phone": "010-0000-0000"})
    garbage = client.post(PHONE_URL, json={"name": "홍길동", "phone": "abc"})
    assert ok.status_code == wrong_name.status_code == unknown.status_code == garbage.status_code == 204
    assert ok.content == wrong_name.content == unknown.content == garbage.content == b""
    [message] = mail_outbox
    assert message.to == "user01@example.com" and message.template == "login_id" and "user01" in message.text


def test_find_id_by_phone_sends_one_mail_per_matching_account(client, db, make_user, mail_outbox):
    make_user("user01", name="홍길동", phone="010-1234-5678")
    make_user("user02", name="홍길동", phone="01012345678")  # 가족이 같은 번호를 쓰는 경우
    blocked = make_user("user03", name="홍길동", phone="010-1234-5678")
    blocked.is_active = False
    db.commit()
    client.post(PHONE_URL, json={"name": "홍길동", "phone": "010-1234-5678"})
    assert sorted(m.to for m in mail_outbox) == ["user01@example.com", "user02@example.com"]
    client.post(PHONE_URL, json={"name": "홍길동", "phone": "010-1234-5678"})  # 60초 안: 조용히 건너뜀
    assert len(mail_outbox) == 2


# ---- 인증번호·소셜 ----


def test_email_verification_found_by_hash(db):
    from app.auth import repository as auth_repository

    now = datetime.now(UTC)
    row = EmailVerification(email_hash=email_index("code@example.com"), code_hash="x" * 64, expires_at=now, created_at=now)
    db.add(row)
    db.commit()
    assert "email" not in _cols(db, "email_verifications")
    assert auth_repository.latest_pending_email_code(db, "CODE@example.com").id == row.id


def test_social_account_email_is_encrypted(db):
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
    assert "email" not in _cols(db, "social_accounts")


# ---- 로그 안전망 ----


def test_log_filter_masks_email_and_phone():
    assert redact_pii("to=kim.minji@example.com tel 010-1234-5678") == "to=k***@example.com tel [전화번호]"
    assert redact_pii("user_id=12 code=123456 2026-11-17") == "user_id=12 code=123456 2026-11-17"
    record = logging.LogRecord("app.x", logging.INFO, __file__, 1, "메일 %s", ("a@example.com",), None)
    record.path = "/api/x?email=b@example.com"
    PiiRedactFilter().filter(record)
    assert record.getMessage() == "메일 a***@example.com" and record.path == "/api/x?email=b***@example.com"

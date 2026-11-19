"""관리자 멤버 목록은 개인정보를 가려서, 한 명 보기(GET /users/{id})만 전체 값을 보여 줍니다 (계획 23 D7)"""

from datetime import date

from app.users import pii

PROFILE = {
    "phone": "010-1234-5678",
    "postcode": "06236",
    "address": "서울 강남구 테헤란로 123",
    "address_detail": "4층 401호",
    "birth_date": date(1995, 4, 12),
    "gender": "female",
    "nickname": "행복한미어캣",
}


def test_list_masks_personal_fields_and_detail_shows_all(client, make_user, login):
    make_user("admin01", admin=True)
    target = make_user("member01", email="member.one@example.com", name="회원하나", **PROFILE)
    headers = login("admin01")

    [item] = client.get("/api/users", headers=headers, params={"q": "member01"}).json()["items"]
    assert item["email"] == "me********@example.com"
    assert item["phone"] == "010-****-5678"
    assert item["postcode"] == "06***"
    assert item["address"] == "서울 강남구 ***"
    assert item["address_detail"] == "***"
    assert item["birth_date"] == "1995-**-**"
    # 암호화하지 않는 항목은 그대로
    assert (item["name"], item["nickname"], item["gender"]) == ("회원하나", "행복한미어캣", "female")
    for value in ("1234", "테헤란로", "401호", "04-12", "06236"):
        assert value not in str(item)

    detail = client.get(f"/api/users/{target.id}", headers=headers).json()
    assert detail["email"] == "member.one@example.com" and detail["phone"] == "010-1234-5678"
    assert detail["postcode"] == "06236" and detail["address"] == "서울 강남구 테헤란로 123"
    assert detail["address_detail"] == "4층 401호" and detail["birth_date"] == "1995-04-12"


def test_list_keeps_empty_fields_empty(client, make_user, login):
    make_user("admin01", admin=True)
    make_user("member02")
    [item] = client.get("/api/users", headers=login("admin01"), params={"q": "member02"}).json()["items"]
    assert [item[k] for k in ("phone", "postcode", "address", "address_detail", "birth_date")] == [None] * 5


def test_role_and_active_changes_still_return_full_values(client, make_user, login):
    """목록이 아닌 한 명 응답(역할 변경 등)은 상세와 같음"""
    make_user("admin01", admin=True)
    target = make_user("member01", **PROFILE)
    body = client.patch(f"/api/users/{target.id}/active", headers=login("admin01"), json={"is_active": False}).json()
    assert body["phone"] == "010-1234-5678"


def test_mask_helpers():
    assert pii.mask_phone("010-1234-5678") == "010-****-5678"
    assert pii.mask_phone("02-123-4567") == "02-***-4567"
    assert pii.mask_phone("+1 650-253-0000") == "+1 650-***-0000"  # 앞 묶음(지역 번호)과 끝 4자리만
    assert pii.mask_phone("12-34") == "*****"
    assert pii.mask_phone(None) is None
    assert pii.mask_place("서울 강남구 테헤란로 123", keep_words=2) == "서울 강남구 ***"
    assert pii.mask_place("세종", keep_words=2) == "***"
    assert pii.mask_place("06236", keep_chars=2) == "06***"
    assert pii.mask_place("4층 401호") == "***"
    assert pii.mask_place(None) is None

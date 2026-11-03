"""매무새 개인 AI 키 (11/03): 암호화 저장·끝 4자리만 응답, 스위치가 켜지면 누른 사람의 키로 분석, 서버 키로 대신 돌리지 않음"""

import logging
from contextlib import nullcontext
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select, update

from app.core.config import settings as core_settings
from app.features.maemusae.ai_keys.models import UserAiKey
from app.features.maemusae.analysis import runner
from app.features.maemusae.config import mms_settings, production_problems
from app.features.maemusae.retention.service import purge_withdrawn_ai_keys
from app.llm.errors import translate
from app.users.models import User

URL = "/api/mms/me/ai-key"
PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}
KEY = "sk-test-abcdefghijklmnopqrstuvwxyz-WXYZ"
OTHER_KEY = "sk-test-zzzzzzzzzzzzzzzzzzzzzzzzzz-1234"


@pytest.fixture(autouse=True)
def _app_logs_visible():
    logger = logging.getLogger("app")
    logger.propagate = True  # 하네스 pytest-app-logging
    yield
    logger.propagate = False


@pytest.fixture(autouse=True)
def _defaults(db, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_ai_key_encryption_key", SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", False)
    monkeypatch.setattr(runner, "open_session", lambda: nullcontext(db))


@pytest.fixture
def headers(db, make_user, login):
    def _headers(login_id: str) -> dict[str, str]:
        if db.scalar(select(User).where(User.login_id == login_id)) is None:
            make_user(login_id)
        return login(login_id)

    return _headers


@pytest.fixture
def owner(headers):
    return headers("owner01")


@pytest.fixture
def docs_url(client, owner):
    project = client.post(PROJECTS, json=PROJECT, headers=owner).json()
    [document] = client.get(f"{PROJECTS}/{project['id']}/documents", headers=owner).json()
    url = f"{PROJECTS}/{project['id']}/documents/{document['id']}"
    assert client.post(f"{url}/sources", data={"text": "회원은 이메일로 가입한다."}, headers=owner).status_code == 201
    return url


@pytest.fixture
def used_keys(monkeypatch, fake_llm):
    """분석이 모델을 만들 때 넘긴 api_key 기록 (가짜 LLM 을 그대로 돌려줌)"""
    keys: list[str | None] = []

    def _get(*, api_key=None, model_name=None):
        keys.append(api_key)
        return fake_llm

    monkeypatch.setattr(runner, "get_chat_model", _get)
    return keys


def _answer():
    return {"requirements": [{"name": "회원 가입", "description": "이메일 가입", "kind": "FUNCTIONAL",
                              "priority": "HIGH", "question": None,
                              "evidence": [{"page": "P1", "quote": "이메일로 가입한다"}]}]}


# ---- 저장·조회·삭제 ----


def test_login_required(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"api_key": KEY}).status_code == 401


def test_save_encrypts_and_returns_only_hint(client, db, owner, caplog):
    assert client.get(URL, headers=owner).json() == {
        "storage_ready": True, "in_use": False, "provider": None, "key_hint": None,
    }

    caplog.set_level(logging.INFO)
    response = client.put(URL, json={"api_key": f"  {KEY} "}, headers=owner)

    assert response.status_code == 200, response.text
    assert response.json() == {"storage_ready": True, "in_use": False, "provider": "openai", "key_hint": "WXYZ"}
    row = db.scalar(select(UserAiKey))
    assert KEY not in row.encrypted_key
    assert KEY not in response.text and KEY not in caplog.text
    assert client.get(URL, headers=owner).json()["key_hint"] == "WXYZ"

    assert client.put(URL, json={"api_key": OTHER_KEY}, headers=owner).json()["key_hint"] == "1234"
    assert db.scalar(select(UserAiKey).where(UserAiKey.key_hint == "1234")) is not None

    assert client.delete(URL, headers=owner).status_code == 204
    assert client.get(URL, headers=owner).json()["key_hint"] is None
    assert client.delete(URL, headers=owner).status_code == 204  # 없어도 같은 응답


def test_keys_are_per_person(client, headers):
    a, b = headers("user0a"), headers("user0b")
    client.put(URL, json={"api_key": KEY}, headers=a)
    assert client.get(URL, headers=b).json()["key_hint"] is None


@pytest.mark.parametrize("bad", ["", "abc", "sk-short", "pk-" + "a" * 30, "sk-has space inside-aaaaaaaaaaaa", "sk-" + "a" * 400])
def test_bad_key_format_is_rejected(client, owner, bad):
    assert client.put(URL, json={"api_key": bad}, headers=owner).status_code == 422


def test_without_encryption_key_saving_is_off(client, owner, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_ai_key_encryption_key", SecretStr(""))
    assert client.get(URL, headers=owner).json()["storage_ready"] is False
    response = client.put(URL, json={"api_key": KEY}, headers=owner)
    assert (response.status_code, response.json()["code"]) == (503, "MMS_AI_KEY_STORAGE_NOT_CONFIGURED")


# ---- 분석에 쓰기 ----


def test_switch_off_uses_server_key(client, owner, docs_url, used_keys, fake_llm):
    client.put(URL, json={"api_key": KEY}, headers=owner)
    fake_llm.responses = [_answer()]

    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["status"] == "SUCCEEDED"
    assert used_keys and set(used_keys) == {None}


def test_switch_on_uses_requester_key(client, owner, docs_url, used_keys, fake_llm, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", True)
    client.put(URL, json={"api_key": KEY}, headers=owner)
    fake_llm.responses = [_answer()]

    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["status"] == "SUCCEEDED"
    assert used_keys and set(used_keys) == {KEY}
    assert runner._run_api_key.get() is None  # 분석이 끝나면 비움


def test_switch_on_without_key_does_not_start(client, owner, docs_url, fake_llm, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", True)

    response = client.post(f"{docs_url}/analyze", json={}, headers=owner)

    assert (response.status_code, response.json()["code"]) == (409, "MMS_AI_KEY_REQUIRED")
    assert "마이페이지" in response.json()["detail"]
    assert fake_llm.calls == []
    assert client.get(f"{docs_url}/analysis", headers=owner).json() is None


def test_key_deleted_after_start_fails_without_server_key(client, db, owner, docs_url, used_keys, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", True)
    client.put(URL, json={"api_key": KEY}, headers=owner)
    real = runner.run_analysis

    def _delete_then_run(run_id):
        db.execute(UserAiKey.__table__.delete())
        real(run_id)

    monkeypatch.setattr(runner, "run_analysis", _delete_then_run)  # 라우터는 부를 때 runner 속성을 읽음

    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202

    progress = client.get(f"{docs_url}/analysis", headers=owner).json()
    assert (progress["status"], progress["error_code"]) == ("FAILED", "MMS_AI_KEY_REQUIRED")
    assert used_keys == []


class AuthenticationError(Exception):
    pass


def test_personal_key_errors_get_personal_codes(client, owner, docs_url, used_keys, fake_llm, monkeypatch):
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", True)
    client.put(URL, json={"api_key": KEY}, headers=owner)
    fake_llm.responses = [translate(AuthenticationError())]

    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["error_code"] == "MMS_AI_KEY_INVALID"


def test_server_key_errors_keep_kit_codes(client, owner, docs_url, used_keys, fake_llm):
    fake_llm.responses = [translate(AuthenticationError())]

    assert client.post(f"{docs_url}/analyze", json={}, headers=owner).status_code == 202

    assert client.get(f"{docs_url}/analysis", headers=owner).json()["error_code"] == "LLM_AUTH_FAILED"


# ---- 정리·운영 검사 ----


def test_withdrawn_users_keys_are_purged(client, db, headers):
    a, b = headers("user0a"), headers("user0b")
    client.put(URL, json={"api_key": KEY}, headers=a)
    client.put(URL, json={"api_key": KEY}, headers=b)
    db.execute(update(User).where(User.login_id == "user0a").values(deactivated_at=datetime.now(UTC)))

    assert purge_withdrawn_ai_keys(db, apply=False) == 1
    assert len(list(db.scalars(select(UserAiKey)))) == 2
    assert purge_withdrawn_ai_keys(db, apply=True) == 1
    [left] = db.scalars(select(UserAiKey))
    assert left.user_id == db.scalar(select(User.id).where(User.login_id == "user0b"))


def test_production_check(monkeypatch):
    monkeypatch.setattr(core_settings, "app_env", "production")
    assert production_problems() == []

    monkeypatch.setattr(mms_settings, "mms_ai_key_encryption_key", SecretStr("not-a-fernet-key"))
    assert len(production_problems()) == 1

    monkeypatch.setattr(mms_settings, "mms_ai_key_encryption_key", SecretStr(""))
    assert production_problems() == []  # 스위치가 꺼져 있으면 키가 없어도 시작 가능
    monkeypatch.setattr(mms_settings, "mms_user_ai_key_enabled", True)
    [problem] = production_problems()
    assert problem.startswith("MMS_AI_KEY_ENCRYPTION_KEY")


def test_key_rotation_keeps_old_keys_readable(client, db, owner, monkeypatch):
    from app.features.maemusae.ai_keys import crypto

    client.put(URL, json={"api_key": KEY}, headers=owner)
    old = mms_settings.mms_ai_key_encryption_key.get_secret_value()
    monkeypatch.setattr(mms_settings, "mms_ai_key_encryption_key", SecretStr(f"{Fernet.generate_key().decode()},{old}"))

    assert crypto.decrypt(db.scalar(select(UserAiKey)).encrypted_key) == KEY

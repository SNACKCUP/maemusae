"""개인 AI 키 저장·조회·삭제, 분석이 쓸 키 꺼내기. 키 원문은 응답·로그에 넣지 않습니다."""

import logging

from sqlalchemy.orm import Session

from app.features.maemusae.ai_keys import crypto, repository
from app.features.maemusae.ai_keys.models import UserAiKey
from app.features.maemusae.ai_keys.schemas import AiKeyRead, AiKeySave
from app.features.maemusae.config import mms_settings
from app.features.maemusae.errors import (
    AiKeyRequiredError,
    AiKeyStorageNotConfiguredError,
)

logger = logging.getLogger(__name__)

HINT_CHARS = 4


def in_use() -> bool:
    """분석이 개인 키로 도는지 (스위치)"""
    return mms_settings.mms_user_ai_key_enabled


def _read(row: UserAiKey | None) -> AiKeyRead:
    return AiKeyRead(
        storage_ready=crypto.is_configured(),
        in_use=in_use(),
        provider=row.provider if row else None,
        key_hint=row.key_hint if row else None,
    )


def get_my_key(db: Session, user_id: int) -> AiKeyRead:
    return _read(repository.get(db, user_id))


def save_my_key(db: Session, user_id: int, body: AiKeySave) -> AiKeyRead:
    if not crypto.is_configured():
        raise AiKeyStorageNotConfiguredError()
    encrypted = crypto.encrypt(body.api_key)
    hint = body.api_key[-HINT_CHARS:]
    row = repository.get(db, user_id)
    if row is None:
        row = UserAiKey(user_id=user_id, provider=body.provider, encrypted_key=encrypted, key_hint=hint)
        repository.add(db, row)
        action = "등록"
    else:
        row.provider, row.encrypted_key, row.key_hint = body.provider, encrypted, hint
        action = "변경"
    db.commit()
    logger.info("개인 AI 키 %s user_id=%s provider=%s", action, user_id, body.provider)
    return _read(row)


def delete_my_key(db: Session, user_id: int) -> None:
    if repository.delete_of_user(db, user_id):
        db.commit()
        logger.info("개인 AI 키 삭제 user_id=%s", user_id)


def require_key(db: Session, user_id: int) -> None:
    """분석·다시 분류 시작 전에 확인. 스위치가 켜져 있는데 키가 없으면 409 (시작하지 않음)"""
    if in_use() and repository.get(db, user_id) is None:
        raise AiKeyRequiredError()


def key_for_run(db: Session, user_id: int) -> str | None:
    """뒤에서 도는 분석이 쓸 키 원문. 스위치가 꺼져 있으면 None (서버 키).

    켜져 있는데 키가 없거나(그사이 지움) 풀 수 없으면 AiKeyRequiredError — 서버 키로 대신 돌리지 않습니다.
    """
    if not in_use():
        return None
    row = repository.get(db, user_id)
    if row is None:
        raise AiKeyRequiredError()
    try:
        return crypto.decrypt(row.encrypted_key)
    except (crypto.KeyDecryptError, crypto.KeyStorageNotConfiguredError) as e:
        logger.error("개인 AI 키를 풀지 못함 user_id=%s (MMS_AI_KEY_ENCRYPTION_KEY 확인)", user_id)
        raise AiKeyRequiredError() from e

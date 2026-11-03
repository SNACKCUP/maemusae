"""개인 AI 키 테이블 접근. SQL 은 이 파일에만 둡니다. commit 은 service 가 합니다."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.features.maemusae.ai_keys.models import UserAiKey
from app.users.models import User


def get(db: Session, user_id: int) -> UserAiKey | None:
    return db.get(UserAiKey, user_id)


def add(db: Session, row: UserAiKey) -> None:
    db.add(row)
    db.flush()


def delete_of_user(db: Session, user_id: int) -> int:
    return db.execute(delete(UserAiKey).where(UserAiKey.user_id == user_id)).rowcount


def delete_of_withdrawn(db: Session, *, apply: bool) -> int:
    """탈퇴한(deactivated_at 이 있는) 회원의 키. apply=False 면 세기만"""
    withdrawn = select(User.id).where(User.deactivated_at.is_not(None))
    if not apply:
        return len(list(db.scalars(select(UserAiKey.user_id).where(UserAiKey.user_id.in_(withdrawn)))))
    return db.execute(delete(UserAiKey).where(UserAiKey.user_id.in_(withdrawn))).rowcount

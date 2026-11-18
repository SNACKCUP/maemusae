"""기존 회원의 개인정보 암호화 칸 채우기 (계획 23 K2). 여러 번 실행해도 안전합니다.

    uv run python -m app.users.pii_backfill            # 실제 처리
    uv run python -m app.users.pii_backfill --dry-run  # 몇 건 남았는지 세기만

마이그레이션 cfe9930b9cfa 로 칸을 만든 뒤, 새 코드를 배포하고 한 번 실행합니다
(.github/workflows/pii-backfill.yml). 새로 저장하는 회원은 저장할 때 자동으로 채워지므로, 이 명령은 그 전부터 있던 행만 다룹니다.
대상: pii_key_version 이 빈 행. 500건씩 저장하므로 중간에 멈춰도 다시 실행하면 이어서 합니다.
로그에는 건수와 회원 번호(id)만 남깁니다 (값 없음). 키(PII_*)가 필요합니다.
"""

import argparse
import logging
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.users import pii, repository

logger = logging.getLogger("app.users.pii_backfill")

BATCH_SIZE = 500


def backfill(db: Session, *, dry_run: bool = False, batch_size: int = BATCH_SIZE) -> int:
    """채운(또는 dry_run 이면 채울) 회원 수"""
    if dry_run:
        return repository.count_pii_unsynced(db)
    total, last_id = 0, 0
    while True:
        users = repository.pii_unsynced_batch(db, last_id, batch_size)
        if not users:
            break
        for user in users:
            pii.sync_encrypted_fields(user)
        db.commit()  # 배치마다 저장
        total += len(users)
        last_id = users[-1].id
        logger.info("개인정보 암호화 칸 채움 %s건 (마지막 id=%s)", len(users), last_id)
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="처리하지 않고 남은 건수만 출력")
    args = parser.parse_args(argv)
    setup_logging()
    try:
        with SessionLocal() as db:
            count = backfill(db, dry_run=args.dry_run)
            remaining = repository.count_pii_unsynced(db)
            bad_phones = repository.count_phone_without_hash(db)
    except Exception:
        logger.exception("개인정보 암호화 칸 채우기 실패. DATABASE_URL·PII_* 키와 DB 상태를 확인한 뒤 다시 실행하세요.")
        return 1
    action = "대상" if args.dry_run else "처리"
    logger.info("회원 %s %s건, 남은 행 %s건, 형식이 틀려 지문 없는 전화번호 %s건", action, count, remaining, bad_phones)
    return 0


if __name__ == "__main__":
    sys.exit(main())

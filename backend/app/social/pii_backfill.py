"""기존 소셜 연결의 이메일 암호화 칸 채우기 (계획 23 K2). 여러 번 실행해도 안전합니다.

    uv run python -m app.social.pii_backfill            # 실제 처리
    uv run python -m app.social.pii_backfill --dry-run  # 몇 건 남았는지 세기만

app.users.pii_backfill 다음에 실행합니다 (.github/workflows/pii-backfill.yml). 로그에는 건수만 남깁니다.
"""

import argparse
import logging
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.social import repository

logger = logging.getLogger("app.social.pii_backfill")

BATCH_SIZE = 500


def backfill(db: Session, *, dry_run: bool = False, batch_size: int = BATCH_SIZE) -> int:
    if dry_run:
        return repository.count_email_enc_missing(db)
    total, last_id = 0, 0
    while True:
        accounts = repository.email_enc_missing_batch(db, last_id, batch_size)
        if not accounts:
            break
        for account in accounts:
            account.email_enc = account.email
        db.commit()
        total += len(accounts)
        last_id = accounts[-1].id
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="처리하지 않고 남은 건수만 출력")
    args = parser.parse_args(argv)
    setup_logging()
    try:
        with SessionLocal() as db:
            count = backfill(db, dry_run=args.dry_run)
            remaining = repository.count_email_enc_missing(db)
    except Exception:
        logger.exception("소셜 연결 이메일 암호화 칸 채우기 실패. DATABASE_URL·PII_* 키와 DB 상태를 확인한 뒤 다시 실행하세요.")
        return 1
    action = "대상" if args.dry_run else "처리"
    logger.info("소셜 연결 %s %s건, 남은 행 %s건", action, count, remaining)
    return 0


if __name__ == "__main__":
    sys.exit(main())

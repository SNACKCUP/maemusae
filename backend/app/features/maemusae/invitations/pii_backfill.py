"""기존 초대의 이메일 암호화 칸·지문 채우기 (계획 23 M1). 여러 번 실행해도 안전합니다.

    uv run python -m app.features.maemusae.invitations.pii_backfill            # 실제 처리
    uv run python -m app.features.maemusae.invitations.pii_backfill --dry-run  # 몇 건 남았는지 세기만

킷 채우기(app.users·app.social.pii_backfill) 다음에 실행합니다 (.github/workflows/pii-backfill.yml). 로그에는 건수만 남깁니다.
"""

import argparse
import logging
import sys

from sqlalchemy.orm import Session

# 명령으로 따로 실행하면 앱 전체 모델이 올라오지 않으므로, 초대가 가리키는 테이블(mms_projects·users)을 직접 불러옴
import app.features.maemusae.projects.models
import app.users.models  # noqa: F401
from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.features.maemusae.invitations import repository
from app.features.maemusae.invitations.models import fill_email_pii

logger = logging.getLogger("app.features.maemusae.invitations.pii_backfill")

BATCH_SIZE = 500


def backfill(db: Session, *, dry_run: bool = False, batch_size: int = BATCH_SIZE) -> int:
    if dry_run:
        return repository.count_email_pii_missing(db)
    total, last_id = 0, 0
    while True:
        rows = repository.email_pii_missing_batch(db, last_id, batch_size)
        if not rows:
            break
        for inv in rows:
            fill_email_pii(inv)
        db.commit()
        total += len(rows)
        last_id = rows[-1].id
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="처리하지 않고 남은 건수만 출력")
    args = parser.parse_args(argv)
    setup_logging()
    try:
        with SessionLocal() as db:
            count = backfill(db, dry_run=args.dry_run)
            remaining = repository.count_email_pii_missing(db)
    except Exception:
        logger.exception("초대 이메일 암호화 칸 채우기 실패. DATABASE_URL·PII_* 키와 DB 상태를 확인한 뒤 다시 실행하세요.")
        return 1
    action = "대상" if args.dry_run else "처리"
    logger.info("매무새 초대 %s %s건, 남은 행 %s건", action, count, remaining)
    return 0


if __name__ == "__main__":
    sys.exit(main())

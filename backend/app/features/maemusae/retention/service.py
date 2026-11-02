"""보관 기간이 지난 프로젝트 정리. 여러 번 실행해도 안전합니다 (사용법은 retention/__init__.py).

순서: 원본 파일 → DB 행. 원본을 하나라도 못 지우면 그 프로젝트는 건너뛰고 다음 실행 때 다시 시도합니다.
원본을 지운 뒤 DB 삭제가 실패해도, 다음 실행에서 없는 key 를 지우는 것은 문제가 되지 않습니다.
로그에는 프로젝트 id 와 건수만 남깁니다 (프로젝트명·파일 이름·본문 금지).
"""

import argparse
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.features.maemusae.config import mms_settings
from app.features.maemusae.retention import repository
from app.storage import PrivateStorage, get_private_storage
from app.storage.errors import StorageError, StorageObjectNotFoundError

logger = logging.getLogger("app.features.maemusae.retention")


@dataclass
class RetentionResult:
    projects: int = 0  # 지운(dry-run 이면 지울) 프로젝트 수
    files: int = 0  # 지운(dry-run 이면 지울) 원본 파일 수
    skipped: list[int] = field(default_factory=list)  # 원본 삭제에 실패해 건너뛴 프로젝트 id


def purge_deleted_projects(
    db: Session,
    *,
    apply: bool = False,
    now: datetime | None = None,
    storage: PrivateStorage | None = None,
) -> RetentionResult:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=mms_settings.mms_project_retention_days)
    result = RetentionResult()
    for project_id in repository.expired_project_ids(db, cutoff):
        keys = repository.storage_keys_of_project(db, project_id)
        if not apply:
            result.projects += 1
            result.files += len(keys)
            continue
        if keys and not _delete_files(storage or get_private_storage(), project_id, keys):
            result.skipped.append(project_id)
            continue
        try:
            repository.delete_project(db, project_id)
            db.commit()  # 프로젝트마다 따로 커밋해 하나가 실패해도 앞의 정리는 남깁니다
        except Exception:
            db.rollback()
            logger.exception("지운 프로젝트 DB 정리 실패 project_id=%s", project_id)
            result.skipped.append(project_id)
            continue
        result.projects += 1
        result.files += len(keys)
        logger.info("지운 프로젝트 정리 project_id=%s 원본 %s건", project_id, len(keys))
    return result


def _delete_files(storage: PrivateStorage, project_id: int, keys: list[str]) -> bool:
    for key in keys:
        try:
            storage.delete(key)
        except StorageObjectNotFoundError:
            continue  # 이미 없으면 지운 것으로 봅니다
        except StorageError:
            logger.warning("원본 파일 삭제 실패로 다음 실행 때 다시 시도 project_id=%s", project_id)
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="매무새 지운 프로젝트 보관 기간 정리")
    parser.add_argument("--apply", action="store_true", help="실제로 지움 (없으면 대상 건수만 출력)")
    args = parser.parse_args(argv)
    setup_logging()
    try:
        with SessionLocal() as db:
            result = purge_deleted_projects(db, apply=args.apply)
    except Exception:
        logger.exception("매무새 보관 기간 정리 실패. DATABASE_URL·저장소 설정과 DB 상태를 확인한 뒤 다시 실행하세요.")
        return 1
    action = "삭제" if args.apply else "대상"
    logger.info(
        "보관 기간(%s일)이 지난 프로젝트 %s %s건, 원본 파일 %s건, 건너뜀 %s건",
        mms_settings.mms_project_retention_days, action, result.projects, result.files, len(result.skipped),
    )
    # 건너뛴 프로젝트가 있으면 실패로 끝내 워크플로 화면에서 보이게 합니다 (다음 날 다시 시도)
    return 1 if result.skipped else 0

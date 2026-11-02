"""매무새 지운 프로젝트 보관 기간 정리 (app.features.maemusae.retention)"""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.features.maemusae.projects.models import Project, ProjectMember
from app.features.maemusae.retention import service
from app.features.maemusae.retention.service import purge_deleted_projects
from app.storage import errors as storage_errors
from tests.features.maemusae import samples

PROJECTS = "/api/mms/projects"
PROJECT = {"name": "쇼핑몰 리뉴얼", "start_date": "2026-11-01", "end_date": "2026-12-31"}
PDF = samples.pdf(["Members sign up with email.", "Pay by card."])


@pytest.fixture(autouse=True)
def _app_logs_visible():
    # app 로거는 propagate=False 라서 caplog 가 받도록 테스트 동안만 켭니다 (하네스 pytest-app-logging)
    logger = logging.getLogger("app")
    logger.propagate = True
    yield
    logger.propagate = False


@pytest.fixture
def owner(make_user, login):
    make_user("owner01", name="owner01 이름")
    return login("owner01")


@pytest.fixture
def make_project(client, owner, private_storage):
    """원본 파일 1개 + 직접 쓴 글 1개가 있는 프로젝트를 만들고, days 일 전에 지운 것으로 표시"""

    def _make(db, *, days: int | None, name: str = "쇼핑몰_요청서.pdf") -> int:
        project = client.post(PROJECTS, json=PROJECT, headers=owner).json()
        [doc] = client.get(f"{PROJECTS}/{project['id']}/documents", headers=owner).json()
        url = f"{PROJECTS}/{project['id']}/documents/{doc['id']}/sources"
        assert client.post(url, files={"file": (name, PDF, "application/pdf")}, headers=owner).status_code == 201
        assert client.post(url, data={"text": "회의 메모: 관리자는 주문을 취소할 수 있다."}, headers=owner).status_code == 201
        if days is not None:
            deleted_at = datetime.now(UTC) - timedelta(days=days)
            db.execute(update(Project).where(Project.id == project["id"]).values(deleted_at=deleted_at))
            db.commit()
        return project["id"]

    return _make


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_dry_run_counts_only(db, make_project, private_storage):
    expired = make_project(db, days=mms_settings.mms_project_retention_days + 1)

    result = purge_deleted_projects(db)

    assert (result.projects, result.files, result.skipped) == (1, 1, [])
    assert db.get(Project, expired) is not None
    assert len(private_storage.objects) == 1


def test_apply_removes_expired_project_rows_and_originals(db, make_project, private_storage):
    days = mms_settings.mms_project_retention_days
    expired = make_project(db, days=days + 1)
    recent = make_project(db, days=days - 1, name="최근.pdf")  # 보관 기간 안
    live = make_project(db, days=None, name="살아있음.pdf")  # 지우지 않은 프로젝트
    keep_keys = set(db.scalars(select(SourceFile.storage_key).where(SourceFile.storage_key.is_not(None))))
    expired_keys = {
        k for k in db.scalars(
            select(SourceFile.storage_key).join(Document).where(Document.project_id == expired, SourceFile.storage_key.is_not(None))
        )
    }
    keep_keys -= expired_keys

    result = purge_deleted_projects(db, apply=True)

    assert (result.projects, result.files, result.skipped) == (1, 1, [])
    db.expire_all()
    assert db.get(Project, expired) is None
    assert {p.id for p in db.scalars(select(Project))} == {recent, live}
    assert db.scalar(select(func.count()).select_from(Document).where(Document.project_id == expired)) == 0
    assert db.scalar(select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == expired)) == 0
    assert set(private_storage.objects) == keep_keys
    assert _count(db, SourcePage) > 0  # 다른 프로젝트의 쪽 본문은 그대로

    assert purge_deleted_projects(db, apply=True).projects == 0  # 다시 실행해도 안전


def test_storage_failure_skips_project_and_keeps_rows(db, make_project, private_storage, monkeypatch):
    expired = make_project(db, days=mms_settings.mms_project_retention_days + 1)

    def broken(key):
        raise storage_errors.unavailable()

    monkeypatch.setattr(private_storage, "delete", broken)
    result = purge_deleted_projects(db, apply=True)

    assert result.skipped == [expired]
    assert result.projects == 0
    assert db.get(Project, expired) is not None  # 다음 실행 때 다시 시도


def test_missing_original_counts_as_deleted(db, make_project, private_storage):
    expired = make_project(db, days=mms_settings.mms_project_retention_days + 1)
    private_storage.objects.clear()  # 원본이 이미 없음

    assert purge_deleted_projects(db, apply=True).projects == 1
    db.expire_all()
    assert db.get(Project, expired) is None


def test_logs_have_ids_and_counts_only(db, make_project, private_storage, caplog):
    make_project(db, days=mms_settings.mms_project_retention_days + 1, name="비밀_계약서.pdf")

    with caplog.at_level(logging.INFO):
        purge_deleted_projects(db, apply=True)

    text = caplog.text
    assert "project_id=" in text
    for secret in ("비밀_계약서", "쇼핑몰 리뉴얼", "회의 메모", "Members sign up"):
        assert secret not in text


def test_main_exit_codes(monkeypatch):
    monkeypatch.setattr(service, "SessionLocal", lambda: _NullSession())
    monkeypatch.setattr(service, "purge_deleted_projects", lambda db, apply=False: service.RetentionResult())
    assert service.main([]) == 0
    monkeypatch.setattr(service, "purge_deleted_projects", lambda db, apply=False: service.RetentionResult(skipped=[7]))
    assert service.main(["--apply"]) == 1


class _NullSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

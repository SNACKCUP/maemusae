"""매무새 문서·올린 파일 API: 파일 카드, 올리기(파일·직접 쓴 글), 쪽 본문, 원본 내려받기, 지우기, 권한"""

import logging
from urllib.parse import quote

import pytest
from sqlalchemy import select, update

from app.features.maemusae.config import mms_settings
from app.features.maemusae.documents import repository
from app.features.maemusae.documents.models import Document, SourceFile, SourcePage
from app.features.maemusae.projects.models import MEMBER, ProjectMember
from app.users.models import User
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
def headers(db, make_user, login):
    def _headers(login_id: str, *, admin: bool = False) -> dict[str, str]:
        if db.scalar(select(User).where(User.login_id == login_id)) is None:
            make_user(login_id, admin=admin, name=f"{login_id} 이름")
        return login(login_id)

    return _headers


@pytest.fixture
def project(client, headers):
    response = client.post(PROJECTS, json=PROJECT, headers=headers("owner01"))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def docs_url(client, headers, project):
    """요구사항정의서 문서 주소 (프로젝트를 만들면 생김)"""
    [document] = client.get(f"{PROJECTS}/{project['id']}/documents", headers=headers("owner01")).json()
    return f"{PROJECTS}/{project['id']}/documents/{document['id']}"


@pytest.fixture
def member(db, headers, project):
    """member01: 프로젝트 일반 멤버"""

    def _member(login_id: str = "member01") -> dict[str, str]:
        hdrs = headers(login_id)
        user = db.scalar(select(User).where(User.login_id == login_id))
        db.add(ProjectMember(project_id=project["id"], user_id=user.id, role=MEMBER))
        db.commit()
        return hdrs

    return _member


def _upload(client, url, hdrs, data=PDF, name="쇼핑몰_요청서.pdf", content_type="application/pdf"):
    return client.post(f"{url}/sources", files={"file": (name, data, content_type)}, headers=hdrs)


# ---- 파일 카드 ----


def test_creating_project_creates_requirements_document(client, headers, project):
    response = client.get(f"{PROJECTS}/{project['id']}/documents", headers=headers("owner01"))
    assert response.status_code == 200
    [document] = response.json()
    assert document["kind"] == "REQUIREMENTS"
    assert document["kind_label"] == "요구사항정의서"  # 공통코드 MMS_DOC_KIND (마이그레이션이 넣음)
    assert document["status"] == "EMPTY"
    assert document["current_revision"] == 0
    assert document["source_count"] == 0

    one = client.get(f"{PROJECTS}/{project['id']}/documents/{document['id']}", headers=headers("owner01"))
    assert one.json()["id"] == document["id"]
    assert client.get(f"{PROJECTS}/{project['id']}/documents/999999", headers=headers("owner01")).json()["code"] == (
        "DOCUMENT_NOT_FOUND"
    )


def test_mms_codes_are_available_to_screens(client, headers):
    response = client.get("/api/codes/MMS_REQ_KIND", headers=headers("owner01"))
    assert response.status_code == 200, response.text
    assert [c["code"] for c in response.json()["codes"]] == ["FUNCTIONAL", "NON_FUNCTIONAL", "CONSTRAINT"]


# ---- 올리기 ----


def test_upload_pdf_stores_pages_and_private_original(client, headers, docs_url, project, private_storage):
    response = _upload(client, docs_url, headers("owner01"))
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["source_type"] == "FILE"
    assert source["filename"] == "쇼핑몰_요청서.pdf"
    assert source["content_type"] == "application/pdf"
    assert source["size_bytes"] == len(PDF)
    assert source["page_count"] == 2
    assert source["uploaded_by_name"] == "owner01 이름"
    assert source["uploaded_by_me"] is True

    # 원본은 비공개 저장소에. key 에 파일 이름을 넣지 않음
    [(key, (data, content_type))] = private_storage.objects.items()
    assert key.startswith(f"mms/projects/{project['id']}/sources/")
    assert "요청서" not in key
    assert data == PDF and content_type == "application/pdf"

    pages = client.get(f"{docs_url}/sources/{source['id']}/pages", headers=headers("owner01")).json()
    assert [(p["seq"], p["page_no"], p["location_label"], p["text"]) for p in pages] == [
        (1, 1, "1쪽", "Members sign up with email."),
        (2, 2, "2쪽", "Pay by card."),
    ]

    listed = client.get(f"{docs_url}/sources", headers=headers("owner01")).json()
    assert [s["id"] for s in listed] == [source["id"]]
    assert client.get(docs_url, headers=headers("owner01")).json()["source_count"] == 1


def test_download_original_streams_from_private_storage(client, headers, docs_url, private_storage):
    source = _upload(client, docs_url, headers("owner01")).json()
    response = client.get(f"{docs_url}/sources/{source['id']}/file", headers=headers("owner01"))
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert f"filename*=UTF-8''{quote('쇼핑몰_요청서.pdf')}" in disposition
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_text_source_is_one_page_without_original(client, headers, docs_url, private_storage):
    response = client.post(f"{docs_url}/sources", data={"text": "  관리자는 주문을 취소할 수 있다.  "}, headers=headers("owner01"))
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["source_type"] == "TEXT"
    assert source["filename"] is None and source["size_bytes"] is None
    assert source["page_count"] == 1
    assert private_storage.objects == {}

    [page] = client.get(f"{docs_url}/sources/{source['id']}/pages", headers=headers("owner01")).json()
    assert page["location_label"] == "직접 입력"
    assert page["text"] == "관리자는 주문을 취소할 수 있다."
    file = client.get(f"{docs_url}/sources/{source['id']}/file", headers=headers("owner01"))
    assert file.status_code == 404


def test_upload_input_rules(client, headers, docs_url, private_storage, monkeypatch):
    hdrs = headers("owner01")
    assert client.post(f"{docs_url}/sources", headers=hdrs).json()["code"] == "SOURCE_INPUT_REQUIRED"
    assert client.post(f"{docs_url}/sources", data={"text": "   "}, headers=hdrs).json()["code"] == "SOURCE_INPUT_REQUIRED"
    both = client.post(
        f"{docs_url}/sources", data={"text": "글"}, files={"file": ("a.pdf", PDF, "application/pdf")}, headers=hdrs
    )
    assert both.json()["code"] == "SOURCE_INPUT_REQUIRED"

    fake = _upload(client, docs_url, hdrs, data=b"<html>", name="a.pdf")
    assert fake.status_code == 415
    assert fake.json()["code"] == "UNSUPPORTED_FILE_TYPE"
    scan = _upload(client, docs_url, hdrs, data=samples.pdf([""]), name="scan.pdf")
    assert scan.status_code == 422
    assert scan.json()["code"] == "DOCUMENT_PARSE_FAILED"

    monkeypatch.setattr(mms_settings, "mms_source_max_bytes", 100)
    large = _upload(client, docs_url, hdrs)
    assert large.status_code == 413
    assert large.json()["code"] == "FILE_TOO_LARGE"
    assert private_storage.objects == {}  # 거절된 파일은 저장소에 올라가지 않음


def test_duplicate_and_limit(client, headers, docs_url, private_storage, monkeypatch):
    hdrs = headers("owner01")
    assert _upload(client, docs_url, hdrs).status_code == 201
    dup = _upload(client, docs_url, hdrs, name="다른이름.pdf")
    assert dup.status_code == 409
    assert dup.json()["code"] == "SOURCE_DUPLICATE"

    monkeypatch.setattr(mms_settings, "mms_sources_per_document", 2)
    assert client.post(f"{docs_url}/sources", data={"text": "둘째"}, headers=hdrs).status_code == 201
    over = client.post(f"{docs_url}/sources", data={"text": "셋째"}, headers=hdrs)
    assert over.status_code == 409
    assert over.json()["code"] == "SOURCE_LIMIT_REACHED"
    assert len(private_storage.objects) == 1


def test_busy_document_blocks_upload_and_delete(client, db, headers, docs_url, private_storage):
    hdrs = headers("owner01")
    source = _upload(client, docs_url, hdrs).json()
    db.execute(update(Document).values(status="ANALYZING"))
    db.commit()
    assert client.post(f"{docs_url}/sources", data={"text": "글"}, headers=hdrs).json()["code"] == "DOCUMENT_BUSY"
    assert client.delete(f"{docs_url}/sources/{source['id']}", headers=hdrs).json()["code"] == "DOCUMENT_BUSY"


def test_storage_not_configured_blocks_files_but_not_text(client, db, headers, docs_url):
    hdrs = headers("owner01")
    response = _upload(client, docs_url, hdrs)
    assert response.status_code == 503
    assert response.json()["code"] == "STORAGE_NOT_CONFIGURED"
    assert db.scalar(select(SourceFile)) is None
    assert client.post(f"{docs_url}/sources", data={"text": "글"}, headers=hdrs).status_code == 201


def test_db_failure_removes_uploaded_original(client, db, headers, docs_url, private_storage, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(repository, "add_all", broken)
    assert _upload(client, docs_url, headers("owner01")).status_code == 500
    assert private_storage.objects == {}  # 저장소에 올린 원본을 지워 DB 와 어긋나지 않음
    assert db.scalar(select(SourceFile)) is None


# ---- 지우기 ----


def test_delete_by_uploader_or_admin_removes_pages_and_original(
    client, db, headers, docs_url, member, private_storage
):
    member_hdrs = member("member01")
    other_hdrs = member("member02")
    source = _upload(client, docs_url, member_hdrs).json()
    url = f"{docs_url}/sources/{source['id']}"

    forbidden = client.delete(url, headers=other_hdrs)  # 다른 일반 멤버
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "SOURCE_DELETE_FORBIDDEN"

    assert client.delete(url, headers=member_hdrs).status_code == 204  # 올린 사람
    assert private_storage.objects == {}
    assert db.scalar(select(SourcePage)) is None
    assert client.delete(url, headers=member_hdrs).json()["code"] == "SOURCE_NOT_FOUND"

    again = _upload(client, docs_url, member_hdrs).json()  # 지운 뒤에는 같은 파일을 다시 올릴 수 있음
    assert client.delete(f"{docs_url}/sources/{again['id']}", headers=headers("owner01")).status_code == 204  # 관리자


# ---- 권한 ----


def test_master_sees_cards_but_not_customer_content(client, headers, docs_url, project, private_storage):
    source = _upload(client, docs_url, headers("owner01")).json()
    master = headers("master01", admin=True)

    assert client.get(f"{PROJECTS}/{project['id']}/documents", headers=master).status_code == 200
    listed = client.get(f"{docs_url}/sources", headers=master)
    assert listed.status_code == 200
    assert listed.json()[0]["uploaded_by_me"] is False
    # 본문·원본·올리기는 멤버만 (멤버가 아니면 프로젝트가 없는 것처럼 404)
    assert client.get(f"{docs_url}/sources/{source['id']}/pages", headers=master).status_code == 404
    assert client.get(f"{docs_url}/sources/{source['id']}/file", headers=master).status_code == 404
    assert client.post(f"{docs_url}/sources", data={"text": "글"}, headers=master).status_code == 404


def test_non_member_and_deleted_project_get_404(client, headers, docs_url, project):
    stranger = headers("stranger01")
    assert client.get(f"{PROJECTS}/{project['id']}/documents", headers=stranger).status_code == 404
    assert client.get(f"{docs_url}/sources", headers=stranger).json()["code"] == "PROJECT_NOT_FOUND"
    assert client.get(f"{PROJECTS}/{project['id']}/documents").status_code == 401

    assert client.delete(f"{PROJECTS}/{project['id']}", headers=headers("owner01")).status_code == 204
    assert client.get(f"{PROJECTS}/{project['id']}/documents", headers=headers("owner01")).status_code == 404


def test_member_can_upload_and_read_pages(client, headers, docs_url, member, private_storage):
    hdrs = member()
    source = _upload(client, docs_url, hdrs, data=samples.docx(["# 1. 개요", "쇼핑몰"]), name="spec.docx").json()
    [page] = client.get(f"{docs_url}/sources/{source['id']}/pages", headers=hdrs).json()
    assert page["location_label"] == "1. 개요"
    assert page["page_no"] is None


def test_logs_have_no_filename_or_text(client, headers, docs_url, private_storage, caplog):
    hdrs = headers("owner01")
    with caplog.at_level(logging.INFO, logger="app.features.maemusae"):
        source = _upload(client, docs_url, hdrs).json()
        client.post(f"{docs_url}/sources", data={"text": "비밀 요구사항 문장"}, headers=hdrs)
        client.get(f"{docs_url}/sources/{source['id']}/file", headers=hdrs)
        client.delete(f"{docs_url}/sources/{source['id']}", headers=hdrs)

    text = caplog.text
    assert "문서 파일 올림" in text and "문서 원본 내려받기" in text and "문서 파일 삭제" in text
    assert "쇼핑몰_요청서" not in text
    assert "Members sign up" not in text and "비밀 요구사항" not in text

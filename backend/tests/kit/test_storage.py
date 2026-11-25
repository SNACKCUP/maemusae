"""저장소 공통 모듈: 설정에 따른 선택과 운영 설정 검사"""

import pytest

from app.core.config import settings
from app.storage import get_private_storage, get_storage
from app.storage.backends import MemoryStorage
from app.storage.config import production_problems, storage_settings
from app.storage.errors import StorageError, StorageNotConfiguredError


def test_empty_backend_is_not_configured(monkeypatch):
    monkeypatch.setattr(storage_settings, "storage_backend", "")
    with pytest.raises(StorageNotConfiguredError):
        get_storage()


def test_s3_without_bucket_is_not_configured(monkeypatch):
    from app.storage.backends import S3Storage

    monkeypatch.setattr(storage_settings, "storage_bucket", "")
    with pytest.raises(StorageNotConfiguredError):
        S3Storage()


def test_memory_backend_roundtrip(monkeypatch):
    monkeypatch.setattr(storage_settings, "storage_backend", "memory")
    storage = get_storage()
    assert isinstance(storage, MemoryStorage)
    storage.put("a/b.txt", b"hi", "text/plain")
    assert storage.public_url("a/b.txt").endswith("/a/b.txt")
    storage.delete("a/b.txt")
    storage.delete("a/b.txt")  # 없는 파일 삭제도 오류 없음
    assert "a/b.txt" not in storage.objects


def test_production_blocks_memory_and_localhost_url(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(storage_settings, "storage_backend", "memory")
    assert any("STORAGE_BACKEND" in p for p in production_problems())

    monkeypatch.setattr(storage_settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_settings, "storage_public_base_url", "http://127.0.0.1:54321/x")
    assert any("STORAGE_PUBLIC_BASE_URL" in p for p in production_problems())

    monkeypatch.setattr(storage_settings, "storage_backend", "")
    assert production_problems() == []  # 비어 있으면 서버는 뜨고 저장 기능만 503


def test_production_blocks_private_bucket_same_as_public(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(storage_settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_settings, "storage_public_base_url", "https://ref.supabase.co/x")
    monkeypatch.setattr(storage_settings, "storage_private_bucket", "meerkit-public")
    assert any("STORAGE_PRIVATE_BUCKET" in p for p in production_problems())
    monkeypatch.setattr(storage_settings, "storage_private_bucket", "meerkit-private")
    assert production_problems() == []


def test_private_storage_not_configured(monkeypatch):
    monkeypatch.setattr(storage_settings, "storage_backend", "")
    with pytest.raises(StorageNotConfiguredError):
        get_private_storage()
    monkeypatch.setattr(storage_settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_settings, "storage_private_bucket", "")
    with pytest.raises(StorageNotConfiguredError):
        get_private_storage()


def test_private_memory_is_separate_from_public(monkeypatch):
    monkeypatch.setattr(storage_settings, "storage_backend", "memory")
    private = get_private_storage()
    private.put("docs/a.pdf", b"secret", "application/pdf")
    assert private.get("docs/a.pdf") == b"secret"
    assert "docs/a.pdf" not in get_storage().objects
    private.delete("docs/a.pdf")
    with pytest.raises(StorageError) as caught:
        private.get("docs/a.pdf")
    assert caught.value.code == "STORAGE_OBJECT_NOT_FOUND"
    assert caught.value.status_code == 404


def _s3(monkeypatch):
    from app.storage.backends import S3Storage

    for name, value in {
        "storage_s3_endpoint_url": "http://127.0.0.1:54321/storage/v1/s3",
        "storage_s3_access_key_id": "test-key",
        "storage_s3_secret_access_key": "test-secret",
        "storage_bucket": "meerkit-public",
        "storage_public_base_url": "http://127.0.0.1:54321/storage/v1/object/public/meerkit-public/",
    }.items():
        monkeypatch.setattr(storage_settings, name, value)
    return S3Storage()


def _s3_private(monkeypatch):
    from app.storage.backends import S3PrivateStorage

    _s3(monkeypatch)
    monkeypatch.setattr(storage_settings, "storage_private_bucket", "meerkit-private")
    return S3PrivateStorage()


def test_s3_put_sends_content_type_and_long_cache(monkeypatch):
    from botocore.stub import Stubber

    storage = _s3(monkeypatch)
    with Stubber(storage.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "meerkit-public",
                "Key": "avatars/a.webp",
                "Body": b"img",
                "ContentType": "image/webp",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
        storage.put("avatars/a.webp", b"img", "image/webp")
        stub.assert_no_pending_responses()
    assert storage.public_url("avatars/a.webp") == (
        "http://127.0.0.1:54321/storage/v1/object/public/meerkit-public/avatars/a.webp"
    )


def test_s3_errors_become_storage_unavailable(monkeypatch):
    from botocore.stub import Stubber

    from app.storage.errors import StorageError

    storage = _s3(monkeypatch)
    with Stubber(storage.client) as stub:
        stub.add_client_error("delete_object", service_error_code="AccessDenied", http_status_code=403)
        with pytest.raises(StorageError) as caught:
            storage.delete("avatars/a.webp")
    assert caught.value.code == "STORAGE_UNAVAILABLE"


def test_s3_private_put_get_use_private_bucket_without_public_url(monkeypatch):
    import io

    from botocore.response import StreamingBody
    from botocore.stub import Stubber

    storage = _s3_private(monkeypatch)
    assert not hasattr(storage, "public_url")
    with Stubber(storage.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "meerkit-private",
                "Key": "docs/a.pdf",
                "Body": b"pdf",
                "ContentType": "application/pdf",
                "CacheControl": "private, no-store",
            },
        )
        stub.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(b"pdf"), 3)},
            {"Bucket": "meerkit-private", "Key": "docs/a.pdf"},
        )
        storage.put("docs/a.pdf", b"pdf", "application/pdf")
        assert storage.get("docs/a.pdf") == b"pdf"
        stub.assert_no_pending_responses()


def test_s3_private_missing_file_is_not_found(monkeypatch):
    from botocore.stub import Stubber

    storage = _s3_private(monkeypatch)
    with Stubber(storage.client) as stub:
        stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
        with pytest.raises(StorageError) as caught:
            storage.get("docs/gone.pdf")
    assert caught.value.code == "STORAGE_OBJECT_NOT_FOUND"


def _pod_identity(monkeypatch):
    """EKS Pod Identity 환경: 버킷·리전만 있고 키·엔드포인트는 없음. boto3 는 환경의 자격 증명을 씁니다 (테스트에선 가짜 값)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "pod-identity-test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "pod-identity-test")
    for name, value in {
        "storage_s3_endpoint_url": "",
        "storage_s3_access_key_id": "",
        "storage_s3_secret_access_key": "",
        "storage_s3_region": "ap-northeast-2",
        "storage_bucket": "uploads",
        "storage_private_bucket": "uploads-private",
        "storage_public_base_url": "https://uploads.s3.ap-northeast-2.amazonaws.com",
    }.items():
        monkeypatch.setattr(storage_settings, name, value)


def test_s3_bucket_only_uploads_without_keys_or_endpoint(monkeypatch):
    from botocore.stub import Stubber

    from app.storage.backends import S3PrivateStorage, S3Storage

    _pod_identity(monkeypatch)
    storage = S3Storage()
    # 엔드포인트를 넘기지 않았으므로 기본 AWS 주소, 키도 설정값이 아닌 환경(Pod Identity 자리)에서 옴
    assert storage.client.meta.endpoint_url == "https://s3.ap-northeast-2.amazonaws.com"
    assert storage.client._request_signer._credentials.access_key == "pod-identity-test"
    with Stubber(storage.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "uploads",
                "Key": "avatars/a.webp",
                "Body": b"img",
                "ContentType": "image/webp",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
        storage.put("avatars/a.webp", b"img", "image/webp")
        stub.assert_no_pending_responses()

    private = S3PrivateStorage()
    with Stubber(private.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "uploads-private",
                "Key": "docs/a.pdf",
                "Body": b"pdf",
                "ContentType": "application/pdf",
                "CacheControl": "private, no-store",
            },
        )
        private.put("docs/a.pdf", b"pdf", "application/pdf")
        stub.assert_no_pending_responses()


def test_s3_key_based_settings_still_passed_to_boto3(monkeypatch):
    storage = _s3(monkeypatch)
    assert storage.client.meta.endpoint_url == "http://127.0.0.1:54321/storage/v1/s3"
    assert storage.client._request_signer._credentials.access_key == "test-key"

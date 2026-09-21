from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.core import readiness
from app.services.storage import (
    InvalidStorageKeyError,
    LocalFileStorage,
    S3Storage,
    StorageConfigurationError,
    create_storage_service,
)


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def test_local_storage_round_trip_and_cleanup(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "uploads")
    storage.ensure_bucket()

    storage.upload("objects/2026/file-id", BytesIO(b"iterflow"), content_type="text/plain")

    assert storage.exists("objects/2026/file-id") is True
    assert storage.get_metadata("objects/2026/file-id").size == 8
    with storage.open("objects/2026/file-id") as stored:
        assert stored.read() == b"iterflow"
    assert storage.generate_download_url("objects/2026/file-id") is None

    storage.delete("objects/2026/file-id")
    assert storage.exists("objects/2026/file-id") is False


@pytest.mark.parametrize(
    "storage_key",
    [
        "../secret",
        "objects/../../secret",
        "/etc/passwd",
        "objects//file",
        "objects/./file",
        "C:\\Windows\\system.ini",
        "",
    ],
)
def test_local_storage_rejects_non_canonical_or_escaping_keys(
    tmp_path: Path,
    storage_key: str,
) -> None:
    storage = LocalFileStorage(tmp_path / "uploads")

    with pytest.raises(InvalidStorageKeyError):
        storage.upload(storage_key, b"blocked")


def test_local_storage_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    storage = LocalFileStorage(root)

    with pytest.raises(InvalidStorageKeyError):
        storage.upload("escape/file-id", b"blocked")
    assert not (outside / "file-id").exists()


def test_local_storage_upload_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "uploads")
    storage.upload("objects/file-id", b"first")
    storage.upload("objects/file-id", b"second")

    with storage.open("objects/file-id") as stored:
        assert stored.read() == b"second"
    assert list((tmp_path / "uploads").rglob(".iterflow-upload-*")) == []


def test_s3_storage_uses_standard_object_calls() -> None:
    client = Mock()
    client.generate_presigned_url.return_value = "https://storage.example/signed"
    stream = BytesIO(b"payload")
    client.get_object.return_value = {"Body": stream}
    last_modified = datetime(2026, 9, 21, tzinfo=UTC)
    client.head_object.return_value = {
        "ContentLength": 7,
        "ContentType": "text/plain",
        "ETag": '"etag"',
        "LastModified": last_modified,
    }
    storage = S3Storage(bucket="iterflow", client=client)

    storage.upload("objects/file-id", b"payload", content_type="text/plain")
    assert storage.exists("objects/file-id") is True
    assert storage.open("objects/file-id") is stream
    metadata = storage.get_metadata("objects/file-id")
    assert metadata.size == 7
    assert metadata.content_type == "text/plain"
    assert metadata.last_modified == last_modified
    assert storage.generate_download_url("objects/file-id", expires_seconds=60) == (
        "https://storage.example/signed"
    )
    storage.delete("objects/file-id")

    client.put_object.assert_called_once_with(
        Bucket="iterflow",
        Key="objects/file-id",
        Body=b"payload",
        ContentType="text/plain",
    )
    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "iterflow", "Key": "objects/file-id"},
        ExpiresIn=60,
    )
    client.delete_object.assert_called_once_with(Bucket="iterflow", Key="objects/file-id")


def test_s3_storage_missing_object_and_bucket_creation() -> None:
    client = Mock()
    client.head_object.side_effect = _client_error("NoSuchKey", "HeadObject")
    client.head_bucket.side_effect = _client_error("404", "HeadBucket")
    storage = S3Storage(bucket="iterflow", region="eu-west-1", client=client)

    assert storage.exists("objects/missing") is False
    storage.ensure_bucket()

    client.create_bucket.assert_called_once_with(
        Bucket="iterflow",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )


def test_s3_readiness_check_is_read_only() -> None:
    client = Mock()
    storage = S3Storage(bucket="iterflow", client=client)

    storage.check_ready()

    client.head_bucket.assert_called_once_with(Bucket="iterflow")
    client.create_bucket.assert_not_called()


def test_ready_endpoint_storage_check_does_not_initialise_s3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_storage = Mock()
    monkeypatch.setattr(
        readiness,
        "get_settings",
        lambda: Mock(storage_driver="s3"),
    )
    monkeypatch.setattr(
        readiness,
        "create_configured_storage",
        lambda _settings: configured_storage,
    )

    readiness.check_storage()

    configured_storage.check_ready.assert_called_once_with()
    configured_storage.ensure_bucket.assert_not_called()


def test_s3_storage_does_not_swallow_authorization_errors() -> None:
    client = Mock()
    client.head_object.side_effect = _client_error("AccessDenied", "HeadObject")
    storage = S3Storage(bucket="iterflow", client=client)

    with pytest.raises(ClientError):
        storage.exists("objects/file-id")


def test_storage_factory_selects_driver(tmp_path: Path) -> None:
    local = create_storage_service("LOCAL", local_storage_path=tmp_path)
    assert isinstance(local, LocalFileStorage)

    with pytest.raises(StorageConfigurationError):
        create_storage_service("s3")
    with pytest.raises(StorageConfigurationError):
        create_storage_service("unknown")

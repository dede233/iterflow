from __future__ import annotations

from pathlib import Path

from app.services.storage.base import StorageService
from app.services.storage.local import LocalFileStorage
from app.services.storage.s3 import S3Storage


class StorageConfigurationError(ValueError):
    pass


def create_storage_service(
    driver: str,
    *,
    local_storage_path: str | Path | None = None,
    s3_endpoint: str | None = None,
    s3_access_key: str | None = None,
    s3_secret_key: str | None = None,
    s3_bucket: str | None = None,
    s3_region: str = "us-east-1",
) -> StorageService:
    normalised_driver = driver.strip().lower()
    if normalised_driver == "local":
        if local_storage_path is None:
            raise StorageConfigurationError("LOCAL_STORAGE_PATH is required for local storage")
        return LocalFileStorage(local_storage_path)
    if normalised_driver == "s3":
        if not s3_bucket:
            raise StorageConfigurationError("S3_BUCKET is required for S3 storage")
        if bool(s3_access_key) != bool(s3_secret_key):
            raise StorageConfigurationError(
                "S3_ACCESS_KEY and S3_SECRET_KEY must be provided together"
            )
        return S3Storage(
            bucket=s3_bucket,
            region=s3_region,
            endpoint=s3_endpoint,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
        )
    raise StorageConfigurationError(f"unsupported storage driver: {driver}")

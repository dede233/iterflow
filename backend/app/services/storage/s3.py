from __future__ import annotations

from datetime import datetime
from typing import Any, BinaryIO, cast

import boto3
from botocore.exceptions import ClientError

from app.services.storage.base import StorageObjectMetadata, StorageService
from app.services.storage.keys import validate_storage_key


class S3Storage(StorageService):
    """Standard S3 API driver, without assumptions about a specific vendor."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "us-east-1",
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        self.bucket = bucket
        self.region = region
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region,
        )

    def upload(
        self,
        storage_key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> None:
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": validate_storage_key(storage_key),
            "Body": data,
        }
        if content_type:
            params["ContentType"] = content_type
        self._client.put_object(**params)

    def delete(self, storage_key: str) -> None:
        self._client.delete_object(
            Bucket=self.bucket,
            Key=validate_storage_key(storage_key),
        )

    def exists(self, storage_key: str) -> bool:
        try:
            self._client.head_object(
                Bucket=self.bucket,
                Key=validate_storage_key(storage_key),
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            if str(error.get("Code")) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def generate_download_url(
        self,
        storage_key: str,
        *,
        expires_seconds: int = 300,
    ) -> str | None:
        if expires_seconds <= 0:
            raise ValueError("expires_seconds must be positive")
        return cast(
            str,
            self._client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": validate_storage_key(storage_key),
                },
                ExpiresIn=expires_seconds,
            ),
        )

    def open(self, storage_key: str) -> BinaryIO:
        response = self._client.get_object(
            Bucket=self.bucket,
            Key=validate_storage_key(storage_key),
        )
        return cast(BinaryIO, response["Body"])

    def get_metadata(self, storage_key: str) -> StorageObjectMetadata:
        response = self._client.head_object(
            Bucket=self.bucket,
            Key=validate_storage_key(storage_key),
        )
        last_modified = response.get("LastModified")
        return StorageObjectMetadata(
            size=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
            etag=response.get("ETag"),
            last_modified=last_modified if isinstance(last_modified, datetime) else None,
        )

    def check_ready(self) -> None:
        """Verify bucket access without creating or otherwise mutating it."""

        self._client.head_bucket(Bucket=self.bucket)

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            error = exc.response.get("Error", {})
            if str(error.get("Code")) not in {"404", "NoSuchBucket", "NotFound"}:
                raise

        params: dict[str, Any] = {"Bucket": self.bucket}
        if self.region != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
        self._client.create_bucket(**params)

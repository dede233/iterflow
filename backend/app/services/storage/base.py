from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


@dataclass(frozen=True, slots=True)
class StorageObjectMetadata:
    size: int
    content_type: str | None = None
    etag: str | None = None
    last_modified: datetime | None = None


class StorageService(ABC):
    """Vendor-neutral interface used by IterFlow business services."""

    @abstractmethod
    def upload(
        self,
        storage_key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, storage_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate_download_url(
        self,
        storage_key: str,
        *,
        expires_seconds: int = 300,
    ) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO:
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, storage_key: str) -> StorageObjectMetadata:
        raise NotImplementedError

    @abstractmethod
    def check_ready(self) -> None:
        """Check that the configured storage namespace is accessible without creating it."""

        raise NotImplementedError

    @abstractmethod
    def ensure_bucket(self) -> None:
        """Explicitly initialise the configured storage namespace when needed."""

        raise NotImplementedError

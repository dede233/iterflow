from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import BinaryIO

from app.services.storage.base import StorageObjectMetadata, StorageService
from app.services.storage.keys import InvalidStorageKeyError, validate_storage_key

_CHUNK_SIZE = 1024 * 1024


class LocalFileStorage(StorageService):
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).expanduser().resolve()

    def _resolve(self, storage_key: str) -> Path:
        key = validate_storage_key(storage_key)
        candidate = (self.root_path / key).resolve(strict=False)
        if not candidate.is_relative_to(self.root_path):
            raise InvalidStorageKeyError("storage key escapes the configured root")
        return candidate

    def upload(
        self,
        storage_key: str,
        data: bytes | BinaryIO,
        *,
        content_type: str | None = None,
    ) -> None:
        del content_type  # File metadata is persisted by the application database.
        destination = self._resolve(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=".iterflow-upload-",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                if isinstance(data, bytes):
                    temporary.write(data)
                else:
                    while chunk := data.read(_CHUNK_SIZE):
                        temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        path.unlink(missing_ok=True)

        parent = path.parent
        while parent != self.root_path:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).is_file()

    def generate_download_url(
        self,
        storage_key: str,
        *,
        expires_seconds: int = 300,
    ) -> str | None:
        self._resolve(storage_key)
        if expires_seconds <= 0:
            raise ValueError("expires_seconds must be positive")
        # Local files must be streamed through an authenticated IterFlow route.
        return None

    def open(self, storage_key: str) -> BinaryIO:
        return self._resolve(storage_key).open("rb")

    def get_metadata(self, storage_key: str) -> StorageObjectMetadata:
        path = self._resolve(storage_key)
        stat = path.stat()
        if not path.is_file():
            raise FileNotFoundError(path)
        return StorageObjectMetadata(size=stat.st_size)

    def ensure_bucket(self) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        if not self.root_path.is_dir():
            raise NotADirectoryError(self.root_path)

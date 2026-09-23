from __future__ import annotations

import hashlib
import io
import logging
import unicodedata
import zipfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import FileObject, User
from app.models.enums import DataScope, StorageDriver
from app.repositories.file_repository import FileRepository
from app.services.storage import StorageService, create_configured_storage

logger = logging.getLogger(__name__)

# Upload guardrails shared by the generic /files endpoint and business attachment
# endpoints. Validate before touching storage so rejected payloads leave no object.
ALLOWED_UPLOAD_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
UPLOAD_EXTENSIONS = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
    "text/plain": {".txt"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def normalize_upload_filename(original_name: str | None) -> str:
    from app.core.exceptions import AppError

    candidate = (original_name or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    cleaned = "".join(char for char in candidate if unicodedata.category(char) != "Cc").strip()
    if not cleaned:
        raise AppError(42222, "文件名不能为空", 422)
    if len(cleaned) > 255:
        raise AppError(42223, "文件名不能超过255个字符", 422)
    return cleaned


def validate_upload(
    *, size: int, mime_type: str | None, original_name: str | None, content: bytes
) -> str:
    from app.core.exceptions import AppError

    safe_name = normalize_upload_filename(original_name)
    if size > MAX_UPLOAD_SIZE:
        raise AppError(42220, "单文件不能超过50MB", 422)
    if mime_type not in ALLOWED_UPLOAD_TYPES:
        raise AppError(42221, "不支持的文件类型", 422)
    extension = PurePosixPath(safe_name).suffix.lower()
    if extension not in UPLOAD_EXTENSIONS[mime_type]:
        raise AppError(42224, "文件扩展名与 MIME 类型不匹配", 422)

    valid = False
    if mime_type == "image/png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif mime_type == "image/jpeg":
        valid = content.startswith(b"\xff\xd8\xff")
    elif mime_type == "image/webp":
        valid = len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    elif mime_type == "application/pdf":
        valid = content.startswith(b"%PDF-")
    elif mime_type == "text/plain":
        try:
            content.decode("utf-8")
            valid = b"\x00" not in content
        except UnicodeDecodeError:
            valid = False
    elif mime_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
            common_ooxml = {"[Content_Types].xml", "_rels/.rels"}
            if mime_type.endswith("wordprocessingml.document"):
                valid = common_ooxml.issubset(names) and "word/document.xml" in names
            else:
                valid = common_ooxml.issubset(names) and "xl/workbook.xml" in names
        except (OSError, zipfile.BadZipFile):
            valid = False
    if not valid:
        raise AppError(42225, "文件内容与声明的 MIME 类型不匹配", 422)
    return safe_name


class FileService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.repository = FileRepository(db)

    def _storage(self, driver: StorageDriver) -> StorageService:
        return create_configured_storage(self.settings, driver)

    @staticmethod
    def _new_storage_key() -> str:
        now = datetime.now(UTC)
        return f"uploads/{now:%Y/%m}/{uuid4().hex}"

    def upload(
        self,
        *,
        content: bytes,
        original_name: str,
        mime_type: str,
        actor: User,
    ) -> FileObject:
        safe_name = validate_upload(
            size=len(content),
            mime_type=mime_type,
            original_name=original_name,
            content=content,
        )
        driver = StorageDriver(self.settings.storage_driver.upper())
        storage = self._storage(driver)
        storage_key = self._new_storage_key()
        storage.upload(storage_key, content, content_type=mime_type)
        item = FileObject(
            storage_key=storage_key,
            original_name=safe_name,
            mime_type=mime_type,
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_driver=driver,
            created_by=actor.id,
            updated_by=actor.id,
        )
        try:
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
        except Exception:
            self.db.rollback()
            try:
                storage.delete(storage_key)
            except Exception:
                logger.exception("failed to compensate storage upload", extra={"key": storage_key})
            raise
        return item

    def get_scoped(self, file_id: int, actor: User, data_scope: DataScope) -> FileObject:
        item = self.repository.get_scoped(file_id, actor.id, data_scope)
        if item is None:
            raise NotFoundError("文件不存在")
        return item

    def exists(self, file_id: int, actor: User, data_scope: DataScope) -> tuple[FileObject, bool]:
        item = self.get_scoped(file_id, actor, data_scope)
        return item, self._storage(item.storage_driver).exists(item.storage_key)

    def open(self, file_id: int, actor: User, data_scope: DataScope) -> tuple[FileObject, BinaryIO]:
        item = self.get_scoped(file_id, actor, data_scope)
        storage = self._storage(item.storage_driver)
        if not storage.exists(item.storage_key):
            raise NotFoundError("文件内容不存在")
        return item, storage.open(item.storage_key)

    def open_authorized_attachment(
        self, file_id: int, *, entity_type: str, entity_id: int
    ) -> tuple[FileObject, BinaryIO]:
        item = self.repository.get_attached_to_entity(file_id, entity_type, entity_id)
        if item is None:
            raise NotFoundError("文件不存在")
        storage = self._storage(item.storage_driver)
        if not storage.exists(item.storage_key):
            raise NotFoundError("文件内容不存在")
        return item, storage.open(item.storage_key)

    def generate_download_url(
        self,
        file_id: int,
        actor: User,
        data_scope: DataScope,
        *,
        expires_seconds: int = 300,
    ) -> str | None:
        item = self.get_scoped(file_id, actor, data_scope)
        storage = self._storage(item.storage_driver)
        if not storage.exists(item.storage_key):
            raise NotFoundError("文件内容不存在")
        return storage.generate_download_url(item.storage_key, expires_seconds=expires_seconds)

    def delete(self, file_id: int, actor: User, data_scope: DataScope) -> None:
        item = self.repository.get_scoped_including_attached(file_id, actor.id, data_scope)
        if item is None:
            raise NotFoundError("文件不存在")
        if self.repository.has_attachments(item.id):
            raise ConflictError("文件已被业务对象引用。不能删除")
        storage = self._storage(item.storage_driver)
        storage_key = item.storage_key

        # Commit the metadata deletion before removing the object. If the database
        # transaction fails, rollback keeps both the row and the physical file. A later
        # storage failure can leave only an unreferenced object (safe to garbage-collect),
        # never a live database row whose content has silently disappeared.
        try:
            self.db.delete(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        try:
            storage.delete(storage_key)
        except Exception:
            logger.exception(
                "file metadata deleted but physical object cleanup failed; object is orphaned",
                extra={"key": storage_key},
            )
            raise

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
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
        driver = StorageDriver(self.settings.storage_driver.upper())
        storage = self._storage(driver)
        storage_key = self._new_storage_key()
        storage.upload(storage_key, content, content_type=mime_type)
        item = FileObject(
            storage_key=storage_key,
            original_name=original_name,
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

    def open(
        self, file_id: int, actor: User, data_scope: DataScope
    ) -> tuple[FileObject, BinaryIO]:
        item = self.get_scoped(file_id, actor, data_scope)
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
        item = self.get_scoped(file_id, actor, data_scope)
        if self.repository.has_attachments(item.id):
            raise ConflictError("文件已被业务对象引用。不能删除")
        storage = self._storage(item.storage_driver)
        storage.delete(item.storage_key)
        try:
            self.db.delete(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

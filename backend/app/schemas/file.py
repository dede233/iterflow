from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StorageDriver


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    storage_key: str
    size: int
    mime_type: str
    sha256: str
    storage_driver: StorageDriver
    created_at: datetime
    created_by: int | None


class FileExistsOut(BaseModel):
    file_id: int
    exists: bool


class AttachmentOut(BaseModel):
    """Business-facing attachment metadata. Never exposes storage_key/path."""

    model_config = ConfigDict(from_attributes=True)

    file_id: int
    original_name: str
    size: int
    mime_type: str
    created_at: datetime
    created_by: int | None

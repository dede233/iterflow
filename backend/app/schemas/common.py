from datetime import datetime
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse[T](BaseModel):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    request_id: str | None = None


class PageResult[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class RevisionPayload(BaseModel):
    revision: int = Field(ge=1)


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: Any | None
    request_id: str | None


class RevisionConflictData(BaseModel):
    current_revision: int | None
    current_updated_at: datetime | None
    current_updated_by: int | None


class RevisionConflictResponse(BaseModel):
    code: Literal[40910]
    message: str
    data: RevisionConflictData
    request_id: str | None

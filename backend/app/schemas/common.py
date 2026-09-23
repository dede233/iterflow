from typing import Any, TypeVar

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

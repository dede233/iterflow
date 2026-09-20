from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    request_id: str | None = None


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class RevisionPayload(BaseModel):
    revision: int = Field(ge=1)

import unicodedata
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.schemas.common import PageResult
from app.services.rich_text import sanitize_requirement_description


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    version_label: str = Field(min_length=1, max_length=100)
    release_date: date
    content: str = Field(min_length=2, max_length=100000)
    important: bool = False
    image_uploads: dict[str, str] = Field(default_factory=dict)

    @field_validator("title", "version_label")
    @classmethod
    def nonempty(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        visible = [
            c for c in value if not c.isspace() and unicodedata.category(c) not in {"Cc", "Cf"}
        ]
        if len(visible) < (2 if info.field_name == "title" else 1) or "\x00" in value:
            raise ValueError("标题和版本标识不能为空或包含空字符")
        return value

    @field_validator("content")
    @classmethod
    def clean(cls, value: str) -> str:
        return sanitize_requirement_description(value, "HTML")


class AnnouncementUpdate(AnnouncementCreate):
    revision: int = Field(ge=1)


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    version_label: str
    release_date: date
    content: str
    important: bool
    revision: int
    published_at: datetime | None
    read_at: datetime | None


class AnnouncementPage(PageResult[AnnouncementOut]):
    unread_count: int
    can_manage: bool


class AnnouncementNotice(BaseModel):
    unread_count: int
    latest: AnnouncementOut | None
    important: AnnouncementOut | None

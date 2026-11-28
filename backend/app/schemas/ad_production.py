import re
import unicodedata
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from fastapi import UploadFile
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    model_validator,
)

from app.models.enums import AdProductionKind, AdProductionStatus
from app.schemas.common import PageResult
from app.schemas.file import AttachmentOut
from app.schemas.release import OffsetISODatetime
from app.services.rich_text import MAX_DESCRIPTION_LENGTH

MAX_IMAGES = 5
MAX_CONTENT_IMAGES = 12
MAX_CONTENT_CHARACTERS = 3000
AdProductionContentFormat = Literal["PLAIN", "HTML"]


def _iso_date(value: object) -> object:
    if isinstance(value, str) and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("日期格式必须为 YYYY-MM-DD")
    return value


AdWorkDate = Annotated[date, BeforeValidator(_iso_date)]


def _as_utc(value: datetime) -> datetime:
    try:
        return value.astimezone(UTC)
    except OverflowError as exc:
        raise ValueError("时间超出有效范围") from exc


AdProductionTimestamp = Annotated[OffsetISODatetime, AfterValidator(_as_utc)]


def validate_visible_text(value: str) -> str:
    if "\x00" in value or not any(
        not char.isspace() and unicodedata.category(char) not in {"Cc", "Cf", "Mn", "Me"}
        for char in value
    ):
        raise ValueError("必须包含可见字符且不能包含空字符")
    return value


AdProductionTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(validate_visible_text),
]
AdProductionIssuer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(validate_visible_text),
]
AdProductionProcessingResult = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
    AfterValidator(validate_visible_text),
]


def validate_plain_content(value: str) -> str:
    value = value.strip()
    if len(value) > MAX_CONTENT_CHARACTERS:
        raise ValueError("工作内容不能超过 3000 个字符")
    return validate_visible_text(value)


class AdProductionForm(BaseModel):
    work_date: AdWorkDate | None = None
    title: AdProductionTitle | None = None
    content: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH, repr=False)
    content_format: AdProductionContentFormat = "PLAIN"
    issuer: AdProductionIssuer | None = None
    due_at: AdProductionTimestamp | None = None
    status: AdProductionStatus
    receiver_id: int | None = Field(default=None, ge=0)
    completed_by_id: int | None = Field(default=None, ge=0)
    cc_user_ids: str | None = Field(
        default=None,
        title="抄送账号",
        description="JSON 数组字符串。元素为账号 ID。新增账号须启用。省略时保留现状。空数组清空。",
    )
    images: list[UploadFile] = Field(default_factory=list, max_length=MAX_IMAGES)
    content_images: list[UploadFile] = Field(
        default_factory=list, max_length=MAX_CONTENT_IMAGES, repr=False
    )


class AdProductionCreateForm(AdProductionForm):
    title: AdProductionTitle
    status: AdProductionStatus = AdProductionStatus.NOT_STARTED
    receiver_id: int = Field(ge=1)
    kind: AdProductionKind = AdProductionKind.MATERIAL


class AdProductionUpdateForm(AdProductionForm):
    work_date: AdWorkDate
    issuer: AdProductionIssuer
    revision: int = Field(ge=1)
    clear_due_at: bool = False
    processing_result: AdProductionProcessingResult | None = None
    remove_image_ids: list[Annotated[int, Field(ge=1)]] = Field(
        default_factory=list, max_length=MAX_IMAGES
    )


class AdProductionStatusChange(BaseModel):
    revision: int = Field(ge=1)
    status: AdProductionStatus
    completed_by_id: int | None = Field(default=None, ge=0)
    processing_result: AdProductionProcessingResult | None = None

    @model_validator(mode="before")
    @classmethod
    def unchanged_kind(cls, value: Any) -> Any:
        if isinstance(value, dict) and "kind" in value:
            raise ValueError("设计申请类型不能修改")
        return value


class AdProductionDesignerOption(BaseModel):
    id: int
    display_name: str


class AdProductionOut(BaseModel):
    id: int
    work_date: date
    title: AdProductionTitle | None = None
    content: str
    content_format: AdProductionContentFormat = "PLAIN"
    issuer: str
    due_at: datetime | None = None
    status: AdProductionStatus
    kind: AdProductionKind = AdProductionKind.MATERIAL
    processing_result: str | None = None
    receiver_id: int | None = None
    receiver_display_name: str | None = None
    completed_by_id: int | None = None
    completed_by_display_name: str | None = None
    cc_users: list[AdProductionDesignerOption] = Field(title="抄送人")
    created_by: int
    publisher_display_name: str | None = None
    created_at: datetime
    updated_at: datetime
    revision: int
    can_delete: bool = False
    can_withdraw: bool = False
    images: list[AttachmentOut]


class AdProductionPage(PageResult[AdProductionOut]):
    pass

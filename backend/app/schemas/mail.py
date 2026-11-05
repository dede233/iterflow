from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MailMode = Literal["ALL", "TASKS", "OFF"]


class MailPreferencesOut(BaseModel):
    revision: int
    mode: MailMode
    email: str | None
    verified: bool
    pending_email: str | None
    smtp_enabled: bool
    notice_acknowledged: bool


class MailNoticeAcknowledge(BaseModel):
    revision: int = Field(ge=1)


class EmailUnbindRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)


class MailPreferenceChange(BaseModel):
    revision: int = Field(ge=1)
    mode: MailMode


class EmailVerificationRequest(BaseModel):
    revision: int = Field(ge=1)
    email: str = Field(
        max_length=254,
        pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$",
    )

    @field_validator("email")
    @classmethod
    def valid_local_part(cls, value: str) -> str:
        local = value.split("@")[0]
        if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
            raise ValueError("邮箱格式不正确")
        return value


class EmailVerificationConfirm(BaseModel):
    revision: int = Field(ge=1)
    code: str = Field(pattern=r"^[0-9]{6}$")


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_id: str
    user_id: int
    channel: str
    status: str
    attempts: int
    last_error: str | None
    next_attempt_at: datetime


class DeliveryRetry(BaseModel):
    attempts: int = Field(ge=0)

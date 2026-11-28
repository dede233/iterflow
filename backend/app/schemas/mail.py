from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.schemas.common import PageResult

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


def _validate_mailbox_local_part(value: str) -> str:
    local = value.split("@")[0]
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise ValueError("邮箱格式不正确")
    return value


MailAddress = Annotated[
    str,
    Field(
        max_length=254,
        pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$",
    ),
    AfterValidator(_validate_mailbox_local_part),
]


class EmailVerificationRequest(BaseModel):
    revision: int = Field(ge=1)
    email: MailAddress


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


class MailDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    RETRY = "RETRY"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNCERTAIN = "UNCERTAIN"


class MailDeliveryKind(StrEnum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    COLLABORATION = "COLLABORATION"


class MailDeliveryItem(BaseModel):
    id: str
    user_id: int
    username: str
    display_name: str
    kind: MailDeliveryKind
    status: MailDeliveryStatus
    attempts: int
    error_code: str | None
    created_at: datetime
    next_attempt_at: datetime | None
    resend_token: str | None
    resend_block_reason: str | None


class MailDeliveryPage(PageResult[MailDeliveryItem]):
    can_resend_mail_deliveries: bool


class MailDeliveryDetail(BaseModel):
    id: str
    username: str
    display_name: str
    kind: MailDeliveryKind
    status: MailDeliveryStatus
    attempts: int
    error_code: str | None
    created_at: datetime
    next_attempt_at: datetime | None
    masked_email: str | None
    event_label: str
    event_created_at: datetime


class MailDeliveryRecipient(BaseModel):
    user_id: int
    display_name: str
    username: str


class MailDeliveryRecipientPage(PageResult[MailDeliveryRecipient]):
    pass


class MailDeliveryResend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resend_token: str = Field(pattern=r"^[0-9a-f]{64}$")

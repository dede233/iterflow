from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import WECOM_MEMBER_USER_ID_MAX_LENGTH, WECOM_MEMBER_USER_ID_PATTERN

WecomMode = Literal["OFF", "TASKS", "ALL"]


class WecomPreferencesOut(BaseModel):
    revision: int = Field(ge=0)
    member_user_id: str | None
    mode: WecomMode
    enabled: bool


class WecomPreferenceChange(BaseModel):
    revision: int = Field(ge=0)
    mode: WecomMode


class WecomBindingChange(BaseModel):
    revision: int = Field(ge=0)
    member_user_id: str | None = Field(
        min_length=1,
        max_length=WECOM_MEMBER_USER_ID_MAX_LENGTH,
        pattern=WECOM_MEMBER_USER_ID_PATTERN,
    )

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import FeedbackStatus
from app.schemas.feedback import FeedbackCreate


class OnlineReviewConfirm(BaseModel):
    revision: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def reject_nul(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("确认说明不能包含 NUL 字符")
        return value


class OnlineReviewConfirmation(BaseModel):
    confirmed_by: int
    confirmed_by_name: str
    confirmed_at: datetime
    note: str | None


class OnlineReviewFeedbackCreate(FeedbackCreate):
    revision: int = Field(ge=1)


class OnlineReviewFeedbackItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feedback_no: str
    title: str
    status: FeedbackStatus
    created_at: datetime


class OnlineReviewOut(BaseModel):
    revision: int
    can_confirm: bool
    confirmation: OnlineReviewConfirmation | None
    feedbacks: list[OnlineReviewFeedbackItem]
    feedback_total: int

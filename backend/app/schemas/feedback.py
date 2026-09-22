from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    FeedbackConvertType,
    FeedbackStatus,
    FeedbackType,
    FeedbackUrgency,
    ManualFeedbackStatus,
    Priority,
)
from app.schemas.common import PageResult


class FeedbackCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    feedback_type: FeedbackType
    urgency: FeedbackUrgency = FeedbackUrgency.NORMAL
    system_id: int | None = None
    module_id: int | None = None
    description: str = Field(min_length=2)
    expected_result: str | None = None
    actual_result: str | None = None
    reproduce_steps: str | None = None


class FeedbackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    feedback_type: FeedbackType | None = None
    urgency: FeedbackUrgency | None = None
    system_id: int | None = None
    module_id: int | None = None
    description: str | None = Field(default=None, min_length=2)
    expected_result: str | None = None
    actual_result: str | None = None
    reproduce_steps: str | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_null_for_required_business_fields(self) -> Self:
        for field_name in ("title", "feedback_type", "urgency", "description"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class FeedbackStatusChange(BaseModel):
    # Only human-settable statuses are accepted; downstream statuses are rejected
    # by the enum itself (422) so they can never be set through this API.
    status: ManualFeedbackStatus
    revision: int = Field(ge=1)
    reason: str | None = None
    duplicate_of_id: int | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    feedback_no: str
    title: str
    feedback_type: FeedbackType
    urgency: FeedbackUrgency
    status: FeedbackStatus
    system_id: int | None
    module_id: int | None
    submitter_id: int
    description: str
    expected_result: str | None
    actual_result: str | None
    reproduce_steps: str | None
    main_requirement_id: int | None
    duplicate_of_id: int | None
    created_at: datetime
    updated_at: datetime
    updated_by: int | None
    revision: int


class FeedbackPage(PageResult[FeedbackOut]):
    pass


class FeedbackConvertRequest(BaseModel):
    """Convert a feedback into a requirement (Phase 4).

    CREATE_NEW builds a brand-new requirement from the feedback; LINK_EXISTING
    attaches the feedback to an existing requirement. No version association here
    (that is a later phase).
    """

    type: FeedbackConvertType
    revision: int = Field(ge=1)
    # CREATE_NEW fields
    requirement_title: str | None = Field(default=None, min_length=2, max_length=200)
    requirement_type: str | None = Field(
        default=None, min_length=1, max_length=32, pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    priority: Priority = Priority.P2
    description: str | None = Field(default=None, min_length=2)
    acceptance_criteria: str | None = None
    # LINK_EXISTING field
    requirement_id: int | None = None

    @model_validator(mode="after")
    def check_mode_fields(self) -> Self:
        if self.type is FeedbackConvertType.CREATE_NEW:
            missing = [
                name
                for name in ("requirement_title", "requirement_type", "description")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"CREATE_NEW 需要字段: {', '.join(missing)}")
        else:  # LINK_EXISTING
            if self.requirement_id is None:
                raise ValueError("LINK_EXISTING 需要 requirement_id")
        return self

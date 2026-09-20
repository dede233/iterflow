from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    FeedbackStatus,
    FeedbackType,
    FeedbackUrgency,
    Priority,
)


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
    main_requirement_id: int | None
    revision: int


class FeedbackConvertRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    requirement_type: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z][A-Z0-9_]*$")
    priority: Priority = Priority.P2
    owner_id: int | None = None
    description: str
    acceptance_criteria: str | None = None
    version_id: int | None = None
    revision: int = Field(ge=1)

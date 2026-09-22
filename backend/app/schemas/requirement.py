from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ManualRequirementStatus,
    Priority,
    RequirementSource,
    RequirementStatus,
)
from app.schemas.common import PageResult


class RequirementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    requirement_type: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z][A-Z0-9_]*$")
    priority: Priority = Priority.P2
    system_id: int | None = None
    module_id: int | None = None
    owner_id: int | None = None
    description: str
    acceptance_criteria: str | None = None
    version_id: int | None = None


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    requirement_type: str | None = Field(
        default=None, min_length=1, max_length=32, pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    priority: Priority | None = None
    system_id: int | None = None
    module_id: int | None = None
    owner_id: int | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_null_for_required_business_fields(self) -> Self:
        for field_name in ("title", "requirement_type", "priority", "description"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class RequirementStatusChange(BaseModel):
    status: ManualRequirementStatus
    revision: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=2, max_length=500)


class RequirementAssigneeChange(BaseModel):
    owner_id: int | None
    revision: int = Field(ge=1)


class RequirementMoveVersion(BaseModel):
    target_version_id: int
    reason: str = Field(min_length=2, max_length=500)
    revision: int = Field(ge=1)


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requirement_no: str
    title: str
    requirement_type: str
    source: RequirementSource
    priority: Priority
    status: RequirementStatus
    system_id: int | None
    module_id: int | None
    owner_id: int | None
    current_version_id: int | None
    description: str
    acceptance_criteria: str | None
    created_at: datetime
    updated_at: datetime
    updated_by: int | None
    revision: int


class RequirementPage(PageResult[RequirementOut]):
    pass


class LinkedFeedbackOut(BaseModel):
    """A feedback linked to a requirement (source traceability)."""

    model_config = ConfigDict(from_attributes=True)
    feedback_id: int
    feedback_no: str
    title: str
    status: str
    is_primary: bool

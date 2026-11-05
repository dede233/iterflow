from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DesignStatus = Literal["NOT_REQUIRED", "PENDING", "IN_PROGRESS", "DONE"]


class WorkflowAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    action: Literal[
        "CONFIRM",
        "REOPEN",
        "REQUEST_CHANGES",
        "DESIGN_PENDING",
        "DESIGN_START",
        "DESIGN_DONE",
        "DESIGN_CANCEL",
    ]
    reason: str | None = Field(default=None, max_length=500)


class WorkflowRecord(BaseModel):
    id: str
    action: str
    actor_id: int | None
    created_at: datetime
    detail: dict


class WorkflowOut(BaseModel):
    revision: int
    content_revision: int
    confirmed_revision: int | None
    needs_confirmation: bool
    legacy_completed: bool
    design_status: DesignStatus
    paused_from: str | None
    records: list[WorkflowRecord]

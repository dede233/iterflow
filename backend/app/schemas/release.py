from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReleaseResult
from app.schemas.common import PageResult


class ReleaseOut(BaseModel):
    """A release RECORD (record-type entity). Produced only by the publish
    transaction; it has no independent workflow/state of its own."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    version_id: int
    released_at: datetime
    result: ReleaseResult
    release_notes: str
    rollback_notes: str | None
    created_at: datetime
    created_by: int | None
    revision: int


class ReleasePage(PageResult[ReleaseOut]):
    pass


class PublishResult(BaseModel):
    """Outcome of a successful version publish transaction."""

    release: ReleaseOut
    version_id: int
    released_requirement_ids: list[int]
    online_feedback_ids: list[int]


class BlockingRequirement(BaseModel):
    id: int
    requirement_no: str
    status: str


class PublishCheckItem(BaseModel):
    type: str
    passed: bool
    message: str
    blocking_requirements: list[BlockingRequirement] = []


class PublishCheckResult(BaseModel):
    passed: bool
    checks: list[PublishCheckItem]

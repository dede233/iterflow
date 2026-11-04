from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ManualVersionStatus, VersionStatus
from app.schemas.common import PageResult
from app.schemas.requirement import RequirementOut


class VersionCreate(BaseModel):
    version_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    owner_id: int | None = None
    planned_release_date: date | None = None
    description: str | None = None
    requirement_id: int | None = Field(
        default=None,
        ge=1,
        title="关联需求 ID",
        description=(
            "创建时关联的现有需求，必须与 requirement_revision 成对提供；"  # noqa: RUF001
            "不关联时同时为空或省略。"
        ),
    )
    requirement_revision: int | None = Field(
        default=None,
        ge=1,
        title="关联需求版本号",
        description="关联需求的当前 revision，必须与 requirement_id 成对提供。",  # noqa: RUF001
    )

    @model_validator(mode="after")
    def require_paired_requirement_fields(self) -> Self:
        if (self.requirement_id is None) != (self.requirement_revision is None):
            raise ValueError("requirement_id 与 requirement_revision 必须成对提供")
        return self


class VersionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    owner_id: int | None = None
    planned_release_date: date | None = None
    description: str | None = None
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_null_name(self) -> Self:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class VersionStatusChange(BaseModel):
    status: ManualVersionStatus
    revision: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=2, max_length=500)


class AddRequirementRequest(BaseModel):
    requirement_id: int
    # The requirement's own revision (optimistic lock on current_version_id).
    revision: int = Field(ge=1)
    # The Version aggregate revision. Relationship edits change the version's
    # content, so clients must also protect against a stale requirement list.
    version_revision: int = Field(ge=1)


class RemoveRequirementRequest(BaseModel):
    revision: int = Field(ge=1)
    version_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class MoveRequirementRequest(BaseModel):
    requirement_id: int
    revision: int = Field(ge=1)
    # Revision of the target Version. The source Version is locked and bumped
    # by the service as part of the same transaction.
    version_revision: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)


class PublishVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    released_at: datetime
    release_notes: str = Field(min_length=1)
    revision: int = Field(ge=1)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version_no: str
    name: str
    status: VersionStatus
    owner_id: int | None
    planned_release_date: date | None
    released_at: datetime | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    updated_by: int | None
    revision: int


class VersionPage(PageResult[VersionOut]):
    pass


class VersionStats(BaseModel):
    total: int
    by_status: dict[str, int]
    completed: int
    completion_rate: float


class VersionRequirementsOut(BaseModel):
    version_id: int
    stats: VersionStats
    items: list[RequirementOut]


class BulkRequirementItem(BaseModel):
    requirement_id: int = Field(ge=1)
    revision: int = Field(ge=1)


class BulkAddRequirements(BaseModel):
    version_revision: int = Field(ge=1)
    request_id: UUID
    items: list[BulkRequirementItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_requirements(self) -> Self:
        if len({i.requirement_id for i in self.items}) != len(self.items):
            raise ValueError("不能重复选择需求")
        return self

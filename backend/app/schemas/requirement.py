from pydantic import BaseModel, ConfigDict, Field


class RequirementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    requirement_type: str
    priority: str = "P2"
    system_id: int | None = None
    module_id: int | None = None
    owner_id: int | None = None
    description: str
    acceptance_criteria: str | None = None
    version_id: int | None = None


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    requirement_type: str | None = None
    priority: str | None = None
    system_id: int | None = None
    module_id: int | None = None
    owner_id: int | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    revision: int = Field(ge=1)


class RequirementStatusChange(BaseModel):
    status: str
    revision: int = Field(ge=1)


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
    source: str
    priority: str
    status: str
    system_id: int | None
    module_id: int | None
    owner_id: int | None
    current_version_id: int | None
    description: str
    acceptance_criteria: str | None
    revision: int

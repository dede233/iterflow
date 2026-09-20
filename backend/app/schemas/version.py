from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class VersionCreate(BaseModel):
    version_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    owner_id: int | None = None
    planned_release_date: date | None = None
    description: str | None = None


class VersionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    owner_id: int | None = None
    planned_release_date: date | None = None
    description: str | None = None
    revision: int = Field(ge=1)


class VersionStatusChange(BaseModel):
    status: str
    revision: int = Field(ge=1)


class AddRequirementRequest(BaseModel):
    requirement_id: int
    revision: int = Field(ge=1)


class PublishVersionRequest(BaseModel):
    released_at: datetime
    result: str = "SUCCESS"
    release_notes: str = Field(min_length=1)
    revision: int = Field(ge=1)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    version_no: str
    name: str
    status: str
    owner_id: int | None
    planned_release_date: date | None
    released_at: datetime | None
    description: str | None
    revision: int

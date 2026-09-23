from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import (
    DataScope,
    ReleaseResult,
    VersionStatus,
)

type DashboardDataScope = Literal[DataScope.SELF, DataScope.ALL]
type DashboardActiveVersionStatus = Literal[
    VersionStatus.PLANNING,
    VersionStatus.DEVELOPING,
    VersionStatus.TESTING,
    VersionStatus.READY,
]
type DashboardReleaseResult = Literal[ReleaseResult.SUCCESS]


class DashboardFeedbackOverview(BaseModel):
    pending_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    by_status: dict[str, int]


class DashboardRequirementOverview(BaseModel):
    active_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    by_status: dict[str, int]


class DashboardVersionItem(BaseModel):
    id: int
    version_no: str
    name: str
    status: DashboardActiveVersionStatus
    planned_release_date: date | None
    updated_at: datetime


class DashboardVersionOverview(BaseModel):
    active_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    by_status: dict[str, int]
    recent_active_versions: list[DashboardVersionItem] = Field(max_length=5)


class DashboardReleaseItem(BaseModel):
    id: int
    version_id: int
    version_no: str
    version_name: str
    released_at: datetime
    result: DashboardReleaseResult


class DashboardReleaseOverview(BaseModel):
    total_count: int = Field(ge=0)
    recent_releases: list[DashboardReleaseItem] = Field(max_length=5)


class DashboardOverviewOut(BaseModel):
    data_scope: DashboardDataScope
    feedback: DashboardFeedbackOverview | None
    requirements: DashboardRequirementOverview | None
    versions: DashboardVersionOverview | None
    releases: DashboardReleaseOverview | None

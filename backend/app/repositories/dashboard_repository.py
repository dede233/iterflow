from datetime import datetime
from typing import NamedTuple

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Feedback, Release, Requirement, Version
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    ReleaseResult,
    RequirementStatus,
    VersionStatus,
)


class DashboardReleaseRecord(NamedTuple):
    id: int
    version_id: int
    version_no: str
    version_name: str
    released_at: datetime
    result: ReleaseResult


class DashboardRepository:
    """Fixed-query dashboard aggregates with data-scope predicates in SQL."""

    PENDING_FEEDBACK_STATUSES = frozenset(
        {
            FeedbackStatus.NEW,
            FeedbackStatus.ACCEPTED,
        }
    )
    ACTIVE_REQUIREMENT_STATUSES = frozenset(
        {
            RequirementStatus.CONFIRMED,
            RequirementStatus.PLANNED,
            RequirementStatus.DEVELOPING,
            RequirementStatus.TESTING,
        }
    )
    ACTIVE_VERSION_STATUSES = frozenset(
        {
            VersionStatus.PLANNING,
            VersionStatus.DEVELOPING,
            VersionStatus.TESTING,
            VersionStatus.READY,
        }
    )

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _feedback_scope(user_id: int, data_scope: DataScope) -> list[ColumnElement[bool]]:
        return [] if data_scope is DataScope.ALL else [Feedback.submitter_id == user_id]

    @staticmethod
    def _requirement_scope(user_id: int, data_scope: DataScope) -> list[ColumnElement[bool]]:
        if data_scope is DataScope.ALL:
            return []
        return [or_(Requirement.owner_id == user_id, Requirement.created_by == user_id)]

    @staticmethod
    def _version_scope(user_id: int, data_scope: DataScope) -> list[ColumnElement[bool]]:
        if data_scope is DataScope.ALL:
            return []
        return [or_(Version.owner_id == user_id, Version.created_by == user_id)]

    def feedback_status_counts(
        self, user_id: int, data_scope: DataScope
    ) -> dict[FeedbackStatus, int]:
        rows = self.db.execute(
            select(Feedback.status, func.count(Feedback.id))
            .where(*self._feedback_scope(user_id, data_scope))
            .group_by(Feedback.status)
        ).all()
        return {status: int(count) for status, count in rows}

    def requirement_status_counts(
        self, user_id: int, data_scope: DataScope
    ) -> dict[RequirementStatus, int]:
        rows = self.db.execute(
            select(Requirement.status, func.count(Requirement.id))
            .where(*self._requirement_scope(user_id, data_scope))
            .group_by(Requirement.status)
        ).all()
        return {status: int(count) for status, count in rows}

    def version_status_counts(
        self, user_id: int, data_scope: DataScope
    ) -> dict[VersionStatus, int]:
        rows = self.db.execute(
            select(Version.status, func.count(Version.id))
            .where(*self._version_scope(user_id, data_scope))
            .group_by(Version.status)
        ).all()
        return {status: int(count) for status, count in rows}

    def recent_active_versions(
        self, user_id: int, data_scope: DataScope, limit: int = 5
    ) -> list[Version]:
        return list(
            self.db.scalars(
                select(Version)
                .where(
                    *self._version_scope(user_id, data_scope),
                    Version.status.in_(self.ACTIVE_VERSION_STATUSES),
                )
                .order_by(Version.updated_at.desc(), Version.id.desc())
                .limit(limit)
            ).all()
        )

    def release_total_count(self, user_id: int, data_scope: DataScope) -> int:
        return int(
            self.db.scalar(
                select(func.count(Release.id))
                .select_from(Release)
                .join(Version, Version.id == Release.version_id)
                .where(*self._version_scope(user_id, data_scope))
            )
            or 0
        )

    def recent_releases(
        self, user_id: int, data_scope: DataScope, limit: int = 5
    ) -> list[DashboardReleaseRecord]:
        rows = self.db.execute(
            select(
                Release.id,
                Release.version_id,
                Version.version_no,
                Version.name,
                Release.released_at,
                Release.result,
            )
            .join(Version, Version.id == Release.version_id)
            .where(*self._version_scope(user_id, data_scope))
            .order_by(Release.released_at.desc(), Release.id.desc())
            .limit(limit)
        ).all()
        return [DashboardReleaseRecord(*row) for row in rows]

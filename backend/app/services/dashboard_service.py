from typing import cast

from sqlalchemy.orm import Session

from app.models.enums import DataScope, FeedbackStatus, RequirementStatus, VersionStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.user_repository import UserRepository
from app.schemas.dashboard import (
    DashboardActiveVersionStatus,
    DashboardActivityEntityType,
    DashboardActivityItem,
    DashboardDataScope,
    DashboardFeedbackOverview,
    DashboardOverviewOut,
    DashboardReleaseItem,
    DashboardReleaseOverview,
    DashboardReleaseResult,
    DashboardRequirementOverview,
    DashboardVersionItem,
    DashboardVersionOverview,
)


class DashboardService:
    """Build an overview without allowing dashboard.view to widen domain access."""

    def __init__(self, db: Session):
        self.users = UserRepository(db)
        self.dashboard = DashboardRepository(db)
        self.audit = AuditRepository(db)

    @staticmethod
    def _can_view(permissions: set[str], code: str) -> bool:
        return "*" in permissions or code in permissions

    def overview(self, user_id: int) -> DashboardOverviewOut:
        permissions = self.users.permission_codes(user_id)
        data_scope = self.users.data_scope(user_id)
        if data_scope not in {DataScope.SELF, DataScope.ALL}:
            raise RuntimeError("TEAM data scope is reserved and unsupported in V1.5")

        feedback = None
        if self._can_view(permissions, "rd.feedback.view"):
            feedback_counts = self.dashboard.feedback_status_counts(user_id, data_scope)
            by_status = {status.value: feedback_counts.get(status, 0) for status in FeedbackStatus}
            feedback = DashboardFeedbackOverview(
                pending_count=sum(
                    feedback_counts.get(status, 0)
                    for status in DashboardRepository.PENDING_FEEDBACK_STATUSES
                ),
                total_count=sum(feedback_counts.values()),
                by_status=by_status,
            )

        requirements = None
        if self._can_view(permissions, "rd.requirement.view"):
            requirement_counts = self.dashboard.requirement_status_counts(user_id, data_scope)
            by_status = {
                status.value: requirement_counts.get(status, 0) for status in RequirementStatus
            }
            requirements = DashboardRequirementOverview(
                active_count=sum(
                    requirement_counts.get(status, 0)
                    for status in DashboardRepository.ACTIVE_REQUIREMENT_STATUSES
                ),
                total_count=sum(requirement_counts.values()),
                by_status=by_status,
            )

        versions = None
        if self._can_view(permissions, "rd.version.view"):
            version_counts = self.dashboard.version_status_counts(user_id, data_scope)
            by_status = {status.value: version_counts.get(status, 0) for status in VersionStatus}
            versions = DashboardVersionOverview(
                active_count=sum(
                    version_counts.get(status, 0)
                    for status in DashboardRepository.ACTIVE_VERSION_STATUSES
                ),
                total_count=sum(version_counts.values()),
                by_status=by_status,
                recent_active_versions=[
                    DashboardVersionItem(
                        id=version.id,
                        version_no=version.version_no,
                        name=version.name,
                        status=cast(DashboardActiveVersionStatus, version.status),
                        planned_release_date=version.planned_release_date,
                        updated_at=version.updated_at,
                    )
                    for version in self.dashboard.recent_active_versions(user_id, data_scope)
                ],
            )

        releases = None
        if self._can_view(permissions, "rd.release.view"):
            releases = DashboardReleaseOverview(
                total_count=self.dashboard.release_total_count(user_id, data_scope),
                recent_releases=[
                    DashboardReleaseItem(
                        id=release.id,
                        version_id=release.version_id,
                        version_no=release.version_no,
                        version_name=release.version_name,
                        released_at=release.released_at,
                        result=cast(DashboardReleaseResult, release.result),
                    )
                    for release in self.dashboard.recent_releases(user_id, data_scope)
                ],
            )

        activity_types = {
            entity_type
            for entity_type, permission in (
                ("FEEDBACK", "rd.feedback.view"),
                ("REQUIREMENT", "rd.requirement.view"),
                ("VERSION", "rd.version.view"),
                ("RELEASE", "rd.release.view"),
            )
            if self._can_view(permissions, permission)
        }
        activities = [
            DashboardActivityItem(
                entity_type=cast(DashboardActivityEntityType, item.entity_type),
                entity_id=cast(int, item.entity_id),
                action=item.action,
                created_at=item.created_at,
            )
            for item in self.audit.list_recent_scoped(
                user_id=user_id, data_scope=data_scope, entity_types=activity_types, limit=15
            )
        ]

        return DashboardOverviewOut(
            data_scope=cast(DashboardDataScope, data_scope),
            feedback=feedback,
            requirements=requirements,
            versions=versions,
            releases=releases,
            activities=activities,
        )

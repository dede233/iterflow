"""Version progress is a read-only projection of its active requirements.

Only RELEASED/CANCELED are persisted lifecycle decisions. Legacy nonterminal
Version.status values stay readable in storage but never override this policy.
"""

from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, case, not_, or_, select

from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import RequirementStatus, VersionStatus

TERMINAL_VERSION_STATES = frozenset({VersionStatus.RELEASED, VersionStatus.CANCELED})
STARTED_REQUIREMENT_STATES = frozenset(
    {
        RequirementStatus.DESIGNING,  # Historical data before the design substage migration.
        RequirementStatus.DEVELOPING,
        RequirementStatus.TESTING,
        RequirementStatus.DONE,
        RequirementStatus.ONLINE,  # Anomalous in a live version; never publishable.
    }
)
ACCEPTANCE_REQUIREMENT_STATES = frozenset({RequirementStatus.TESTING, RequirementStatus.DONE})


def requirement_confirmed(item: Requirement) -> bool:
    return bool(
        item.legacy_completed
        or (
            item.confirmed_revision is not None and item.confirmed_revision == item.content_revision
        )
    )


def loaded_version_status(item: Version) -> VersionStatus:
    """Read the repository projection without touching mapped ORM attributes."""
    return VersionStatus(item.__dict__["_effective_status"])


def effective_version_status(
    stored_status: str, requirements: Sequence[Requirement]
) -> VersionStatus:
    status = VersionStatus(stored_status)
    if status in TERMINAL_VERSION_STATES:
        return status
    active = [item for item in requirements if item.deleted_at is None]
    if not active:
        return VersionStatus.PLANNING
    if all(
        item.status == RequirementStatus.DONE and requirement_confirmed(item) for item in active
    ):
        return VersionStatus.READY
    if all(item.status in ACCEPTANCE_REQUIREMENT_STATES for item in active):
        return VersionStatus.TESTING
    if any(
        item.status in STARTED_REQUIREMENT_STATES
        or (
            item.status == RequirementStatus.PAUSED
            and item.paused_from in STARTED_REQUIREMENT_STATES
        )
        for item in active
    ):
        return VersionStatus.DEVELOPING
    return VersionStatus.PLANNING


def effective_version_status_expression() -> ColumnElement[str]:
    """Equivalent SQL projection for pagination, filters and dashboard counts.

    Use the authoritative relation and all active requirements, independent of
    a viewer's requirement scope. No hidden requirement details are returned.
    """
    active = (
        select(Requirement.id)
        .join(VersionRequirement, VersionRequirement.requirement_id == Requirement.id)
        .where(
            VersionRequirement.version_id == Version.id,
            VersionRequirement.active.is_(True),
            Requirement.deleted_at.is_(None),
        )
        .correlate(Version)
    )
    any_active = active.exists()
    confirmed = or_(
        Requirement.legacy_completed.is_(True),
        and_(
            Requirement.confirmed_revision.is_not(None),
            Requirement.confirmed_revision == Requirement.content_revision,
        ),
    )
    publish_blocker = active.where(
        or_(Requirement.status != RequirementStatus.DONE, not_(confirmed))
    ).exists()
    before_acceptance = active.where(
        Requirement.status.not_in(ACCEPTANCE_REQUIREMENT_STATES)
    ).exists()
    started = active.where(
        or_(
            Requirement.status.in_(STARTED_REQUIREMENT_STATES),
            and_(
                Requirement.status == RequirementStatus.PAUSED,
                Requirement.paused_from.in_(STARTED_REQUIREMENT_STATES),
            ),
        )
    ).exists()
    return case(
        (Version.status.in_(TERMINAL_VERSION_STATES), Version.status),
        (and_(any_active, not_(publish_blocker)), VersionStatus.READY.value),
        (and_(any_active, not_(before_acceptance)), VersionStatus.TESTING.value),
        (started, VersionStatus.DEVELOPING.value),
        else_=VersionStatus.PLANNING.value,
    )

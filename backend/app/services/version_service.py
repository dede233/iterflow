from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import (
    Feedback,
    Notification,
    Release,
    Requirement,
    RequirementFeedback,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    ManualVersionStatus,
    NotificationType,
    ReleaseResult,
    RequirementStatus,
    VersionStatus,
)
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.version import (
    AddRequirementRequest,
    MoveRequirementRequest,
    PublishVersionRequest,
    RemoveRequirementRequest,
    VersionCreate,
    VersionStatusChange,
    VersionUpdate,
)
from app.services.audit_service import AuditService
from app.services.publish_check_service import PublishCheckService

# Version states in which the requirement set is frozen (V1.5 §freeze).
FROZEN_VERSION_STATES = {VersionStatus.READY, VersionStatus.RELEASED, VersionStatus.CANCELED}
# Requirement statuses counted as "completed" for progress stats.
COMPLETED_REQUIREMENT_STATES = {RequirementStatus.DONE, RequirementStatus.ONLINE}


def _jsonable(value: Any) -> Any:
    """Make audit before/after values JSON-serialisable (dates -> ISO strings)."""
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


VERSION_TRANSITIONS: dict[VersionStatus, set[ManualVersionStatus]] = {
    VersionStatus.PLANNING: {
        ManualVersionStatus.DEVELOPING,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.DEVELOPING: {
        ManualVersionStatus.TESTING,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.TESTING: {
        ManualVersionStatus.DEVELOPING,
        ManualVersionStatus.READY,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.READY: {ManualVersionStatus.TESTING},
    VersionStatus.RELEASED: set(),
    VersionStatus.CANCELED: set(),
}


class VersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VersionRepository(db)
        self.audit = AuditService(db)

    def create(self, payload: VersionCreate, operator_id: int) -> Version:
        item = Version(created_by=operator_id, updated_by=operator_id, **payload.model_dump())
        self.db.add(item)
        self.db.flush()
        self.audit.log("VERSION", item.id, "CREATE", after={"version_no": item.version_no})
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, version_id: int, payload: VersionUpdate, operator_id: int) -> Version:
        current = self.repo.get(version_id)
        if not current:
            raise NotFoundError("版本不存在")
        values = payload.model_dump(exclude_unset=True, exclude={"revision"}) | {
            "updated_by": operator_id
        }
        # Snapshot real old values before the atomic UPDATE (synchronize_session
        # would otherwise mutate this in-session object).
        changed_fields = [key for key in values if key != "updated_by"]
        before_values = {key: _jsonable(getattr(current, key)) for key in changed_fields}
        after_values = {key: _jsonable(values[key]) for key in changed_fields}
        if not self.repo.update_with_revision(version_id, payload.revision, values):
            latest = self.repo.get(version_id)
            if not latest:
                raise NotFoundError("版本不存在")
            raise ConflictError(
                "版本已被其他用户修改",
                {
                    "current_revision": latest.revision,
                    "current_updated_at": latest.updated_at.isoformat(),
                    "current_updated_by": latest.updated_by,
                },
            )
        self.audit.log("VERSION", version_id, "UPDATE", before=before_values, after=after_values)
        self.db.commit()
        updated = self.repo.get(version_id)
        assert updated is not None
        return updated

    def change_status(
        self, version_id: int, payload: VersionStatusChange, operator_id: int
    ) -> Version:
        current = self.repo.get(version_id)
        if not current:
            raise NotFoundError("版本不存在")
        current_status = VersionStatus(current.status)
        previous_status = current.status  # capture before the atomic UPDATE mutates it
        if payload.status not in VERSION_TRANSITIONS[current_status]:
            raise AppError(40921, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if (
            current.status == VersionStatus.READY
            and payload.status == ManualVersionStatus.TESTING
            and (not payload.reason or not payload.reason.strip())
        ):
            raise AppError(42222, "READY 退回 TESTING 必须填写原因", 422)
        if not self.repo.update_with_revision(
            version_id,
            payload.revision,
            {"status": VersionStatus(payload.status.value), "updated_by": operator_id},
        ):
            raise ConflictError("版本状态已发生变化")
        self.audit.log(
            "VERSION",
            version_id,
            "STATUS_CHANGE",
            before={"status": previous_status},
            after={"status": payload.status, "reason": payload.reason},
        )
        self.db.commit()
        updated = self.repo.get(version_id)
        assert updated is not None
        return updated

    # ------------------------------------------------------------------ #
    # VersionRequirement relationship management (all version<->requirement
    # changes go through here; kept transactional and in sync with the
    # Requirement.current_version_id fast-index).
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ensure_mutable(version: Version) -> None:
        if VersionStatus(version.status) in FROZEN_VERSION_STATES:
            raise AppError(40930, f"版本处于 {version.status}，需求清单已冻结", 409)  # noqa: RUF001

    @staticmethod
    def _planned_status(current: str) -> RequirementStatus:
        if RequirementStatus(current) in {RequirementStatus.DRAFT, RequirementStatus.CONFIRMED}:
            return RequirementStatus.PLANNED
        return RequirementStatus(current)

    def requirements_view(self, version_id: int) -> tuple[list[Requirement], dict[str, Any]]:
        requirements = self.repo.active_requirements(version_id)
        by_status: dict[str, int] = {}
        completed = 0
        for req in requirements:
            by_status[str(req.status)] = by_status.get(str(req.status), 0) + 1
            if RequirementStatus(req.status) in COMPLETED_REQUIREMENT_STATES:
                completed += 1
        total = len(requirements)
        stats = {
            "total": total,
            "by_status": by_status,
            "completed": completed,
            "completion_rate": round(completed / total, 4) if total else 0.0,
        }
        return requirements, stats

    def _requirement_conflict(
        self, req_repo: RequirementRepository, requirement_id: int
    ) -> ConflictError:
        latest = req_repo.get(requirement_id)
        return ConflictError(
            "需求已被其他用户修改",
            {
                "current_revision": latest.revision if latest else None,
                "current_updated_at": latest.updated_at.isoformat() if latest else None,
                "current_updated_by": latest.updated_by if latest else None,
            },
        )

    def _version_conflict(self, version_id: int) -> ConflictError:
        latest = self.db.scalar(
            select(Version)
            .where(Version.id == version_id)
            .execution_options(populate_existing=True)
        )
        return ConflictError(
            "版本已被其他用户修改",
            {
                "current_revision": latest.revision if latest else None,
                "current_updated_at": latest.updated_at.isoformat() if latest else None,
                "current_updated_by": latest.updated_by if latest else None,
            },
        )

    def _lock_versions(self, version_ids: set[int]) -> dict[int, Version]:
        """Lock Version aggregates in id order to avoid relation-edit races."""
        versions = list(
            self.db.scalars(
                select(Version)
                .where(Version.id.in_(sorted(version_ids)))
                .order_by(Version.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )
        return {version.id: version for version in versions}

    def _lock_version(self, version_id: int, *, message: str = "版本不存在") -> Version:
        version = self._lock_versions({version_id}).get(version_id)
        if version is None:
            raise NotFoundError(message)
        return version

    def _ensure_version_revision(self, version: Version, expected_revision: int) -> None:
        if version.revision != expected_revision:
            raise self._version_conflict(version.id)

    def _bump_version_revision(
        self, version: Version, expected_revision: int, operator_id: int
    ) -> None:
        """Advance a locked Version after its requirement set changes."""
        self._ensure_version_revision(version, expected_revision)
        if not self.repo.update_with_revision(
            version.id, expected_revision, {"updated_by": operator_id}
        ):
            raise self._version_conflict(version.id)
        self.db.refresh(version)

    def _audit_requirement_relation(
        self,
        action: str,
        *,
        version_id: int,
        requirement_id: int,
        before_version_id: int | None,
        before_current_version_id: int | None,
        after_version_id: int | None,
        reason: str | None = None,
    ) -> None:
        after: dict[str, Any] = {
            "requirement_id": requirement_id,
            "version_id": after_version_id,
            "current_version_id": after_version_id,
        }
        if reason is not None:
            after["reason"] = reason
        self.audit.log(
            "VERSION",
            version_id,
            action,
            before={
                "requirement_id": requirement_id,
                "version_id": before_version_id,
                "current_version_id": before_current_version_id,
            },
            after=after,
        )

    def attach_new_requirement(
        self,
        version_id: int,
        requirement: Requirement,
        *,
        version_revision: int | None,
        operator_id: int,
    ) -> None:
        """Attach a just-created Requirement without committing the outer transaction."""
        if version_revision is None:  # schema validation normally catches this.
            raise AppError(42241, "关联版本时必须提供 version_revision", 422)
        version = self._lock_version(version_id, message="目标版本不存在")
        self._ensure_mutable(version)
        self._ensure_version_revision(version, version_revision)

        previous_current_version_id = requirement.current_version_id
        requirement.current_version_id = version_id
        requirement.status = self._planned_status(requirement.status)
        self.db.add(
            VersionRequirement(
                version_id=version_id, requirement_id=requirement.id, added_by=operator_id
            )
        )
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_ADD",
            version_id=version_id,
            requirement_id=requirement.id,
            before_version_id=None,
            before_current_version_id=previous_current_version_id,
            after_version_id=version_id,
        )
        self._bump_version_revision(version, version_revision, operator_id)

    def add_requirement(
        self,
        version_id: int,
        payload: AddRequirementRequest,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Version:
        version = self._lock_version(version_id)
        self._ensure_mutable(version)
        self._ensure_version_revision(version, payload.version_revision)
        req_repo = RequirementRepository(self.db)
        requirement = req_repo.get_scoped(payload.requirement_id, viewer_id, viewer_scope)
        if requirement is None:
            raise NotFoundError("需求不存在")
        existing = self.repo.active_relation_of_requirement(requirement.id)
        if existing is not None:
            if existing.version_id == version_id:
                raise AppError(40931, "需求已在该版本中", 409)
            raise AppError(
                40932,
                "需求已属于其他版本，请使用迁移",  # noqa: RUF001
                409,
                {"version_id": existing.version_id},
            )
        previous_current_version_id = requirement.current_version_id
        if not req_repo.update_with_revision(
            requirement.id,
            payload.revision,
            {
                "current_version_id": version_id,
                "status": self._planned_status(requirement.status),
                "updated_by": operator_id,
            },
        ):
            raise self._requirement_conflict(req_repo, requirement.id)
        self.db.add(
            VersionRequirement(
                version_id=version_id, requirement_id=requirement.id, added_by=operator_id
            )
        )
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_ADD",
            version_id=version_id,
            requirement_id=requirement.id,
            before_version_id=None,
            before_current_version_id=previous_current_version_id,
            after_version_id=version_id,
        )
        self._bump_version_revision(version, payload.version_revision, operator_id)
        self.db.commit()
        self.db.refresh(version)
        return version

    def remove_requirement(
        self,
        version_id: int,
        requirement_id: int,
        payload: RemoveRequirementRequest,
        operator_id: int,
    ) -> Version:
        version = self._lock_version(version_id)
        self._ensure_mutable(version)
        self._ensure_version_revision(version, payload.version_revision)
        relation = self.repo.active_relation(version_id, requirement_id)
        if relation is None:
            raise NotFoundError("该需求不在此版本中")
        req_repo = RequirementRepository(self.db)
        requirement = req_repo.get(requirement_id)
        if requirement is None:
            raise NotFoundError("需求不存在")
        previous_current_version_id = requirement.current_version_id
        if not req_repo.update_with_revision(
            requirement_id,
            payload.revision,
            {"current_version_id": None, "updated_by": operator_id},
        ):
            raise self._requirement_conflict(req_repo, requirement_id)
        now = datetime.now(UTC)
        self.db.execute(
            update(VersionRequirement)
            .where(VersionRequirement.id == relation.id)
            .values(
                active=False,
                removed_at=now,
                removed_by=operator_id,
                removed_reason=payload.reason,
            )
        )
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_REMOVE",
            version_id=version_id,
            requirement_id=requirement_id,
            before_version_id=version_id,
            before_current_version_id=previous_current_version_id,
            after_version_id=None,
            reason=payload.reason,
        )
        self._bump_version_revision(version, payload.version_revision, operator_id)
        self.db.commit()
        self.db.refresh(version)
        return version

    def move_requirement(
        self,
        target_version_id: int,
        payload: MoveRequirementRequest,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Version:
        req_repo = RequirementRepository(self.db)
        requirement = req_repo.get_scoped(payload.requirement_id, viewer_id, viewer_scope)
        if requirement is None:
            raise NotFoundError("需求不存在")

        # Lock the source and target Version aggregates in a deterministic order.
        # If a concurrent move changed the source before we acquired the locks,
        # include that new source and re-read until the relation is stable.
        version_ids = {target_version_id}
        initial_relation = self.repo.active_relation_of_requirement(requirement.id)
        if initial_relation is not None:
            version_ids.add(initial_relation.version_id)
        while True:
            locked_versions = self._lock_versions(version_ids)
            target = locked_versions.get(target_version_id)
            if target is None:
                raise NotFoundError("目标版本不存在")
            old = self.repo.active_relation_of_requirement(requirement.id)
            if old is None or old.version_id in version_ids:
                break
            version_ids.add(old.version_id)

        self._ensure_mutable(target)
        self._ensure_version_revision(target, payload.version_revision)
        old_version_id = old.version_id if old else None
        old_version = locked_versions.get(old_version_id) if old_version_id is not None else None
        if old is not None:
            if old.version_id == target_version_id:
                raise AppError(40933, "需求已在目标版本中", 409)
            if old_version is None:
                raise NotFoundError("原版本不存在")
            self._ensure_mutable(old_version)  # cannot move out of a frozen source

        previous_current_version_id = requirement.current_version_id
        if not req_repo.update_with_revision(
            requirement.id,
            payload.revision,
            {
                "current_version_id": target_version_id,
                "status": self._planned_status(requirement.status),
                "updated_by": operator_id,
            },
        ):
            raise self._requirement_conflict(req_repo, requirement.id)
        now = datetime.now(UTC)
        if old is not None:
            # Close the old active relation BEFORE inserting the new one so the
            # partial unique index (one active version per requirement) holds.
            self.db.execute(
                update(VersionRequirement)
                .where(VersionRequirement.id == old.id)
                .values(
                    active=False,
                    removed_at=now,
                    removed_by=operator_id,
                    removed_reason=payload.reason,
                )
            )
        self.db.add(
            VersionRequirement(
                version_id=target_version_id, requirement_id=requirement.id, added_by=operator_id
            )
        )
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_MOVE",
            version_id=target_version_id,
            requirement_id=requirement.id,
            before_version_id=old_version_id,
            before_current_version_id=previous_current_version_id,
            after_version_id=target_version_id,
            reason=payload.reason,
        )
        self._bump_version_revision(target, payload.version_revision, operator_id)
        if old_version is not None:
            self._bump_version_revision(old_version, old_version.revision, operator_id)
        self.db.commit()
        self.db.refresh(target)
        return target

    def publish(
        self, version_id: int, payload: PublishVersionRequest, operator_id: int
    ) -> dict[str, Any]:
        """The single, atomic version-publish transaction (V1.5).

        READY version + all active requirements DONE -> create a SUCCESS Release
        record, flip Version READY->RELEASED, DONE requirements->ONLINE and their
        REQUIREMENT_LINKED feedbacks->ONLINE, notify submitters, audit. Any
        failure rolls the whole thing back; a version can never end up RELEASED
        without its Release row.
        """
        # Row-lock the version so concurrent publishes serialise (the atomic
        # conditional UPDATE below is the definitive guard; SQLite ignores the lock).
        version = self.db.scalar(select(Version).where(Version.id == version_id).with_for_update())
        if not version:
            raise NotFoundError("版本不存在")

        # Centralized pre-publish checks (same checks as POST /publish/check).
        check = PublishCheckService(self.db).evaluate(version)
        if not check["passed"]:
            raise AppError(
                40923,
                "发布检查未通过",
                409,
                {
                    "checks": check["checks"],
                    "blocking_requirements": PublishCheckService.blocking_requirements(check),
                },
            )

        active_requirements = self.repo.active_requirements(version_id)

        # Atomic READY -> RELEASED (only one publish can win this).
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(Version)
                .where(
                    Version.id == version_id,
                    Version.revision == payload.revision,
                    Version.status == VersionStatus.READY,
                )
                .values(
                    status=VersionStatus.RELEASED,
                    released_at=payload.released_at,
                    updated_by=operator_id,
                    revision=Version.revision + 1,
                )
            ),
        )
        if not result.rowcount:
            self.db.rollback()
            latest = self.repo.get(version_id)
            raise ConflictError(
                "版本已被其他用户修改",
                {"current_revision": latest.revision if latest else None},
            )

        release = Release(
            version_id=version.id,
            released_at=payload.released_at,
            result=ReleaseResult.SUCCESS,
            release_notes=payload.release_notes,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(release)
        self.db.flush()

        requirement_ids = [r.id for r in active_requirements]
        online_requirement_ids: list[int] = []
        online_feedback_ids: list[int] = []
        if requirement_ids:
            online_requirement_ids = list(
                self.db.scalars(
                    update(Requirement)
                    .where(
                        Requirement.id.in_(requirement_ids),
                        Requirement.status == RequirementStatus.DONE,
                    )
                    .values(
                        status=RequirementStatus.ONLINE,
                        updated_by=operator_id,
                        revision=Requirement.revision + 1,
                    )
                    .returning(Requirement.id)
                ).all()
            )
            for rid in online_requirement_ids:
                self.audit.log(
                    "REQUIREMENT",
                    rid,
                    "STATUS_CHANGE",
                    before={"status": RequirementStatus.DONE},
                    after={"status": RequirementStatus.ONLINE},
                )
            if online_requirement_ids:
                feedback_ids = self.db.scalars(
                    select(RequirementFeedback.feedback_id).where(
                        RequirementFeedback.requirement_id.in_(online_requirement_ids)
                    )
                ).all()
                if feedback_ids:
                    # Only feedbacks still awaiting release (REQUIREMENT_LINKED) go ONLINE.
                    online_feedback_ids = list(
                        self.db.scalars(
                            update(Feedback)
                            .where(
                                Feedback.id.in_(feedback_ids),
                                Feedback.status == FeedbackStatus.REQUIREMENT_LINKED,
                            )
                            .values(
                                status=FeedbackStatus.ONLINE,
                                updated_by=operator_id,
                                revision=Feedback.revision + 1,
                            )
                            .returning(Feedback.id)
                        ).all()
                    )
                    for feedback in self.db.scalars(
                        select(Feedback).where(Feedback.id.in_(online_feedback_ids))
                    ).all():
                        self.audit.log(
                            "FEEDBACK",
                            feedback.id,
                            "STATUS_CHANGE",
                            before={"status": FeedbackStatus.REQUIREMENT_LINKED},
                            after={"status": FeedbackStatus.ONLINE},
                        )
                        self.db.add(
                            Notification(
                                user_id=feedback.submitter_id,
                                type=NotificationType.FEEDBACK,
                                title=f"反馈 {feedback.feedback_no} 已上线",
                                content=f"已随版本 {version.version_no} 发布。",
                                entity_type="FEEDBACK",
                                entity_id=feedback.id,
                            )
                        )
        self.audit.log(
            "VERSION",
            version.id,
            "VERSION_PUBLISH",
            before={"status": VersionStatus.READY},
            after={"status": VersionStatus.RELEASED, "release_id": release.id},
        )
        self.audit.log(
            "RELEASE",
            release.id,
            "RELEASE_CREATE",
            after={"version_id": version.id, "result": ReleaseResult.SUCCESS},
        )
        self.db.commit()
        self.db.refresh(release)
        return {
            "release": release,
            "version_id": version.id,
            "released_requirement_ids": online_requirement_ids,
            "online_feedback_ids": online_feedback_ids,
        }

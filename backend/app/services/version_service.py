import re
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.domain.version_progress import TERMINAL_VERSION_STATES, effective_version_status
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
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.version import (
    AddRequirementRequest,
    BulkAddRequirements,
    MoveRequirementRequest,
    PublishVersionRequest,
    RemoveRequirementRequest,
    VersionCreate,
    VersionStatusChange,
    VersionUpdate,
)
from app.services.audit_service import AuditService
from app.services.collaboration_service import CollaborationService
from app.services.publish_check_service import PublishCheckService
from app.services.revision_conflict import revision_conflict_data
from app.services.system_binding_service import SystemBindingService

# Derived READY is a publishability hint, not a persisted roster lock.
FROZEN_VERSION_STATES = TERMINAL_VERSION_STATES
# Requirement statuses counted as "completed" for progress stats.
COMPLETED_REQUIREMENT_STATES = {RequirementStatus.DONE, RequirementStatus.ONLINE}


def _jsonable(value: Any) -> Any:
    """Make audit before/after values JSON-serialisable (dates -> ISO strings)."""
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


VERSION_TRANSITIONS: dict[VersionStatus, set[ManualVersionStatus]] = {
    status: set() if status in TERMINAL_VERSION_STATES else {ManualVersionStatus.CANCELED}
    for status in VersionStatus
}


class VersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VersionRepository(db)
        self.audit = AuditService(db)

    def create(self, payload: VersionCreate, operator_id: int) -> Version:
        try:
            SystemBindingService(self.db).validate_catalog(payload.system_id)
            if payload.requirement_id is not None:
                permissions = UserRepository(self.db).permission_codes(operator_id)
                if "*" not in permissions and not {
                    "rd.version.edit",
                    "rd.requirement.view",
                }.issubset(permissions):
                    raise PermissionDenied()
            if self._version_no_exists(payload.version_no):
                raise self._duplicate_version_no(payload.version_no)
            item = Version(
                created_by=operator_id,
                updated_by=operator_id,
                **payload.model_dump(exclude={"requirement_id", "requirement_revision"}),
            )
            self.db.add(item)
            try:
                self.db.flush()
            except IntegrityError as exc:
                if self._is_version_no_unique_conflict(exc):
                    raise self._duplicate_version_no(payload.version_no) from None
                raise
            self.audit.log("VERSION", item.id, "CREATE", after={"version_no": item.version_no})
            if payload.requirement_id is not None:
                self._attach_existing_to_created_version(item, payload, operator_id)
            self.db.commit()
            self.db.refresh(item)
            return item
        except Exception:
            self.db.rollback()
            raise

    def _version_no_exists(self, version_no: str) -> bool:
        return (
            self.db.scalar(select(Version.id).where(Version.version_no == version_no)) is not None
        )

    @staticmethod
    def _duplicate_version_no(version_no: str) -> AppError:
        return AppError(
            40934,
            f"版本号「{version_no}」已存在，请更换版本号；如需添加需求，请使用已有版本。",  # noqa: RUF001
            409,
            {"field": "version_no", "reason": "duplicate"},
        )

    @staticmethod
    def _is_version_no_unique_conflict(error: IntegrityError) -> bool:
        """Classify only the version-number key, never unrelated FK/unique failures."""
        original = error.orig
        if getattr(original, "sqlstate", None) == "23505":
            return (
                getattr(getattr(original, "diag", None), "constraint_name", None)
                == "ix_rd_version_version_no"
            )
        args = getattr(original, "args", ())
        if args and args[0] == 1062 and len(args) > 1:
            match = re.search(r"for key ['`]([^'`]+)['`]", str(args[1]))
            return match is not None and match.group(1).split(".")[-1] == "ix_rd_version_version_no"
        return (
            getattr(original, "sqlite_errorcode", None) == 2067
            and str(original) == "UNIQUE constraint failed: rd_version.version_no"
        )

    def _attach_existing_to_created_version(
        self, version: Version, payload: VersionCreate, operator_id: int
    ) -> None:
        """Join the new version and existing requirement inside create's transaction."""
        assert payload.requirement_id is not None and payload.requirement_revision is not None
        scope = UserRepository(self.db).data_scope(operator_id)
        query = select(Requirement).where(
            Requirement.id == payload.requirement_id, Requirement.deleted_at.is_(None)
        )
        if scope is not DataScope.ALL:
            query = query.where(RequirementRepository.self_criterion(operator_id))
        requirement = self.db.scalar(
            query.with_for_update().execution_options(populate_existing=True)
        )
        if requirement is None:
            raise NotFoundError("需求不存在")
        req_repo = RequirementRepository(self.db)
        if requirement.revision != payload.requirement_revision:
            raise self._requirement_conflict(req_repo, requirement.id)
        active_relation = self.db.scalar(
            select(VersionRequirement)
            .where(
                VersionRequirement.requirement_id == requirement.id,
                VersionRequirement.active.is_(True),
            )
            .with_for_update()
        )
        if requirement.current_version_id is not None or active_relation is not None:
            raise AppError(40932, "需求已关联版本，请使用已有版本或明确迁移需求", 409)  # noqa: RUF001
        SystemBindingService(self.db).ensure_match(version, requirement, attaching=True)
        if requirement.status in {RequirementStatus.ONLINE, RequirementStatus.CANCELED}:
            raise AppError(40933, "终态需求不能加入版本", 409)
        if not req_repo.update_with_revision(
            requirement.id,
            payload.requirement_revision,
            {"current_version_id": version.id, "updated_by": operator_id},
        ):
            raise self._requirement_conflict(req_repo, requirement.id)
        self.db.add(
            VersionRequirement(
                version_id=version.id, requirement_id=requirement.id, added_by=operator_id
            )
        )
        # MySQL derives current_version_id from the relation; refresh before
        # collecting recipients so the new version owner is included there too.
        self.db.flush()
        self.db.refresh(requirement)
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_ADD",
            operator_id=operator_id,
            version_id=version.id,
            requirement_id=requirement.id,
            before_version_id=None,
            before_current_version_id=None,
            after_version_id=version.id,
        )
        self._bump_version_revision(version, version.revision, operator_id)

    def update(self, version_id: int, payload: VersionUpdate, operator_id: int) -> Version:
        current = self._lock_version(version_id)
        self._ensure_version_revision(current, payload.revision)
        if current.release_frozen and "description" in payload.model_fields_set:
            raise AppError(40986, "首次发布已开始, 版本内容已冻结", 409)
        if "system_id" in payload.model_fields_set and payload.system_id != current.system_id:
            assert payload.system_id is not None  # VersionUpdate rejects explicit null.
            SystemBindingService(self.db).validate_version_change(current, payload.system_id)
        values = payload.model_dump(exclude_unset=True, exclude={"revision"}) | {
            "updated_by": operator_id
        }
        # Snapshot real old values before the atomic UPDATE (synchronize_session
        # would otherwise mutate this in-session object).
        changed_fields = [key for key in values if key != "updated_by"]
        before_values = {key: _jsonable(getattr(current, key)) for key in changed_fields}
        after_values = {key: _jsonable(values[key]) for key in changed_fields}
        if not self.repo.update_with_revision(version_id, payload.revision, values):
            self.db.expire_all()
            latest = self.repo.get(version_id)
            if not latest:
                raise NotFoundError("版本不存在")
            raise ConflictError(
                "版本已被其他用户修改",
                revision_conflict_data(latest),
            )
        self.audit.log("VERSION", version_id, "UPDATE", before=before_values, after=after_values)
        self.db.commit()
        updated = self.repo.get(version_id)
        assert updated is not None
        return updated

    def change_status(
        self, version_id: int, payload: VersionStatusChange, operator_id: int
    ) -> Version:
        current = self._lock_version(version_id)
        if current.revision != payload.revision:
            raise self._version_conflict(version_id)
        if current.release_frozen and current.status != VersionStatus.RELEASED:
            raise AppError(40986, "首次发布已有实际成功, 不能取消版本", 409)
        current_status = VersionStatus(current.status)
        if payload.status != ManualVersionStatus.CANCELED:
            raise AppError(40921, "版本进度由关联需求自动汇总, 请在需求中推进开发与验收", 409)
        previous_status = effective_version_status(
            current.status, self.repo.active_requirements(version_id)
        )
        if payload.status not in VERSION_TRANSITIONS[current_status]:
            raise AppError(40921, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if not self.repo.update_with_revision(
            version_id,
            payload.revision,
            {"status": VersionStatus(payload.status.value), "updated_by": operator_id},
        ):
            raise self._version_conflict(version_id)
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
        if version.release_frozen:
            raise AppError(40986, "首次发布已开始, 需求清单已冻结", 409)
        if VersionStatus(version.status) in FROZEN_VERSION_STATES:
            raise AppError(40930, f"版本处于 {version.status}，需求清单已冻结", 409)  # noqa: RUF001

    @staticmethod
    def _planned_status(current: str) -> RequirementStatus:
        return RequirementStatus(current)

    def requirements_view(
        self, version_id: int, viewer_id: int, viewer_scope: DataScope
    ) -> tuple[list[Requirement], dict[str, Any]]:
        requirements = self.repo.active_requirements_scoped(version_id, viewer_id, viewer_scope)
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

    @staticmethod
    def _ensure_version_scope(version: Version, viewer_id: int, viewer_scope: DataScope) -> None:
        if viewer_scope is DataScope.ALL:
            return
        if version.owner_id != viewer_id and version.created_by != viewer_id:
            raise NotFoundError("版本不存在")

    def _requirement_conflict(
        self, req_repo: RequirementRepository, requirement_id: int
    ) -> ConflictError:
        self.db.expire_all()
        latest = req_repo.get(requirement_id)
        return ConflictError(
            "需求已被其他用户修改",
            revision_conflict_data(latest),
        )

    def _version_conflict(self, version_id: int) -> ConflictError:
        latest = self.db.scalar(
            select(Version)
            .where(Version.id == version_id)
            .execution_options(populate_existing=True)
        )
        return ConflictError(
            "版本已被其他用户修改",
            revision_conflict_data(latest),
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
        operator_id: int,
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

        self.db.flush()
        requirement = self.db.get(Requirement, requirement_id)
        if requirement is not None:
            CollaborationService(self.db).requirement_event(
                requirement,
                "RELATION_CHANGE",
                operator_id,
            )

    def attach_new_requirement(
        self,
        version_id: int,
        requirement: Requirement,
        *,
        version_revision: int | None,
        operator_id: int,
        viewer_scope: DataScope,
    ) -> None:
        """Attach a just-created Requirement without committing the outer transaction."""
        if version_revision is None:  # schema validation normally catches this.
            raise AppError(42241, "关联版本时必须提供 version_revision", 422)
        version = self._lock_version(version_id, message="目标版本不存在")
        self._ensure_version_scope(version, operator_id, viewer_scope)
        self._ensure_version_revision(version, version_revision)
        self._ensure_mutable(version)

        SystemBindingService(self.db).ensure_match(version, requirement, attaching=True)
        previous_current_version_id = requirement.current_version_id
        if self.db.get_bind().dialect.name != "mysql":
            requirement.current_version_id = version_id
        requirement.status = self._planned_status(requirement.status)
        self.db.add(
            VersionRequirement(
                version_id=version_id, requirement_id=requirement.id, added_by=operator_id
            )
        )
        self._audit_requirement_relation(
            "VERSION_REQUIREMENT_ADD",
            operator_id=operator_id,
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
        self._ensure_version_scope(version, viewer_id, viewer_scope)
        self._ensure_version_revision(version, payload.version_revision)
        self._ensure_mutable(version)
        req_repo = RequirementRepository(self.db)
        requirement = req_repo.get_scoped(payload.requirement_id, viewer_id, viewer_scope)
        if requirement is None:
            raise NotFoundError("需求不存在")
        self.db.refresh(requirement, with_for_update=True)
        if requirement.revision != payload.revision:
            raise self._requirement_conflict(req_repo, requirement.id)
        SystemBindingService(self.db).ensure_match(version, requirement, attaching=True)
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
            operator_id=operator_id,
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

    def bulk_add_requirements(
        self,
        version_id: int,
        payload: BulkAddRequirements,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Version:
        version = self._lock_version(version_id)
        self._ensure_version_scope(version, viewer_id, viewer_scope)
        self._ensure_version_revision(version, payload.version_revision)
        self._ensure_mutable(version)
        expected = {entry.requirement_id: entry.revision for entry in payload.items}
        query = (
            select(Requirement)
            .where(Requirement.id.in_(expected), Requirement.deleted_at.is_(None))
            .order_by(Requirement.id)
        )
        if viewer_scope is not DataScope.ALL:
            query = query.where(RequirementRepository.self_criterion(viewer_id))
        requirements = list(
            self.db.scalars(query.with_for_update().execution_options(populate_existing=True))
        )
        if len(requirements) != len(expected):
            raise NotFoundError("部分需求不存在或不可访问")
        SystemBindingService(self.db).validate_catalog(version.system_id)
        errors = []
        for item in requirements:
            reason = None
            if item.revision != expected[item.id]:
                reason = "需求已修改, 请核对后重新选择"
            elif item.current_version_id is not None or self.repo.active_relation_of_requirement(
                item.id
            ):
                reason = "需求已有版本归属, 请使用迁移"
            elif item.status in {RequirementStatus.ONLINE, RequirementStatus.CANCELED}:
                reason = "终态需求不能加入版本"
            if reason is None:
                reason = SystemBindingService.mismatch(version, item)
            if reason:
                errors.append({"requirement_id": item.id, "reason": reason})
        if errors:
            raise AppError(40933, "批量添加未执行, 请核对所选需求", 409, {"items": errors})
        req_repo = RequirementRepository(self.db)
        for item in requirements:
            if not req_repo.update_with_revision(
                item.id,
                expected[item.id],
                {"current_version_id": version_id, "updated_by": operator_id},
            ):
                raise self._requirement_conflict(req_repo, item.id)
            self.db.add(
                VersionRequirement(
                    version_id=version_id, requirement_id=item.id, added_by=operator_id
                )
            )
            self._audit_requirement_relation(
                "VERSION_REQUIREMENT_ADD",
                operator_id=operator_id,
                version_id=version_id,
                requirement_id=item.id,
                before_version_id=None,
                before_current_version_id=None,
                after_version_id=version_id,
            )
        self._bump_version_revision(version, payload.version_revision, operator_id)
        self.audit.log(
            "VERSION",
            version_id,
            "BULK_ADD",
            after={"request_id": str(payload.request_id), "requirement_ids": sorted(expected)},
        )
        self.db.commit()
        self.db.refresh(version)
        return version

    def remove_requirement(
        self,
        version_id: int,
        requirement_id: int,
        payload: RemoveRequirementRequest,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Version:
        version = self._lock_version(version_id)
        self._ensure_version_scope(version, viewer_id, viewer_scope)
        self._ensure_version_revision(version, payload.version_revision)
        self._ensure_mutable(version)
        req_repo = RequirementRepository(self.db)
        requirement = req_repo.get_scoped(requirement_id, viewer_id, viewer_scope)
        if requirement is None:
            raise NotFoundError("需求不存在")
        if requirement.revision != payload.revision:
            raise self._requirement_conflict(req_repo, requirement.id)
        relation = self.repo.active_relation(version_id, requirement_id)
        if relation is None:
            raise NotFoundError("该需求不在此版本中")
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
            operator_id=operator_id,
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
            self._ensure_version_scope(target, viewer_id, viewer_scope)
            old = self.repo.active_relation_of_requirement(requirement.id)
            if old is None or old.version_id in version_ids:
                break
            version_ids.add(old.version_id)

        old_version_id = old.version_id if old else None
        old_version = locked_versions.get(old_version_id) if old_version_id is not None else None
        if old is not None:
            if old_version is None:
                raise NotFoundError("原版本不存在")
            self._ensure_version_scope(old_version, viewer_id, viewer_scope)

        self._ensure_version_revision(target, payload.version_revision)
        self._ensure_mutable(target)
        self.db.refresh(requirement, with_for_update=True)
        SystemBindingService(self.db).ensure_match(target, requirement, attaching=True)
        if requirement.revision != payload.revision:
            raise self._requirement_conflict(req_repo, requirement.id)
        if old is not None and old_version is not None:
            if old.version_id == target_version_id:
                raise AppError(40933, "需求已在目标版本中", 409)
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
            operator_id=operator_id,
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
        self,
        version_id: int,
        payload: PublishVersionRequest,
        operator_id: int,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        try:
            return self._publish(version_id, payload, operator_id, commit=commit)
        except Exception:
            self.db.rollback()
            raise

    def _publish(
        self,
        version_id: int,
        payload: PublishVersionRequest,
        operator_id: int,
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        """The single, atomic version-publish transaction (V1.5).

        Derived READY + all active requirements DONE -> create a SUCCESS Release
        record, flip Version to RELEASED, DONE requirements->ONLINE and their
        REQUIREMENT_LINKED feedbacks->ONLINE, notify submitters, audit. Any
        failure rolls the whole thing back; a version can never end up RELEASED
        without its Release row.
        """
        # Row-lock the version so concurrent publishes serialise (the atomic
        # conditional UPDATE below is the definitive guard; SQLite ignores the lock).
        version = self.db.scalar(
            select(Version)
            .where(Version.id == version_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not version:
            raise NotFoundError("版本不存在")
        if version.revision != payload.revision:
            raise self._version_conflict(version_id)

        from app.services.target_release_service import TargetReleaseService

        target_service = TargetReleaseService(self.db)
        coverage = target_service.prepare_publish(version, payload, operator_id)

        # Same version -> requirement lock order as workflow/content changes.
        self.db.execute(
            select(Requirement)
            .where(Requirement.current_version_id == version_id)
            .order_by(Requirement.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()
        # Centralized pre-publish checks (same checks as POST /publish/check).
        check = PublishCheckService(self.db).evaluate(version, lock=True, viewer_id=operator_id)
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

        # The locked projection established READY; legacy stored nonterminal
        # status is not authoritative. CAS + terminal guard allow one publish.
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(Version)
                .where(
                    Version.id == version_id,
                    Version.revision == payload.revision,
                    Version.status.not_in(TERMINAL_VERSION_STATES),
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
                revision_conflict_data(latest),
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
            if self.db.get_bind().dialect.name == "mysql":
                online_requirement_ids = self._mysql_online_ids(
                    Requirement,
                    requirement_ids,
                    RequirementStatus.DONE,
                    RequirementStatus.ONLINE,
                    operator_id,
                )
            else:
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
                requirement = self.db.get(Requirement, rid)
                assert requirement is not None
                CollaborationService(self.db).requirement_event(
                    requirement, "PUBLISHED", operator_id
                )
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
                    if self.db.get_bind().dialect.name == "mysql":
                        online_feedback_ids = self._mysql_online_ids(
                            Feedback,
                            list(feedback_ids),
                            FeedbackStatus.REQUIREMENT_LINKED,
                            FeedbackStatus.ONLINE,
                            operator_id,
                        )
                    else:
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
                        CollaborationService(self.db).event(
                            "FEEDBACK",
                            feedback.id,
                            "PUBLISHED",
                            operator_id,
                            [
                                feedback.submitter_id,
                                *CollaborationService(self.db).recipient_ids(feedback.id),
                            ],
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
        if coverage is not None:
            system_id, targets = coverage
            target_service.append_coverage(
                version,
                system_id,
                targets,
                payload.released_at,
                operator_id,
                kind="INITIAL",
                notes=payload.release_notes,
            )
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(release)
        return {
            "release": release,
            "version_id": version.id,
            "released_requirement_ids": online_requirement_ids,
            "online_feedback_ids": online_feedback_ids,
        }

    def _mysql_online_ids(
        self, model: type[Requirement] | type[Feedback], candidates, before, after, operator_id
    ) -> list[int]:
        """Replace RETURNING with current reads and CAS under transaction row locks."""
        rows = self.db.execute(
            select(model.id, model.revision)
            .where(model.id.in_(candidates), model.status == before)
            .order_by(model.id)
            .with_for_update()
        ).all()
        ids: list[int] = []
        for entity_id, revision in rows:
            result = self.db.execute(
                update(model)
                .where(model.id == entity_id, model.revision == revision, model.status == before)
                .values(status=after, updated_by=operator_id, revision=model.revision + 1)
                .execution_options(synchronize_session=False)
            )
            if cast(CursorResult[Any], result).rowcount != 1:
                raise ConflictError("发布对象已被其他事务修改")
            ids.append(entity_id)
        # ORM identity-map objects used for notifications must reflect actual DB updates.
        self.db.expire_all()
        return ids

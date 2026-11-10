from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    ReleaseBatch,
    Requirement,
    Version,
    VersionRequirement,
)


class SystemBindingService:
    """Directory validation and version ownership policy. Call inside the writer transaction."""

    def __init__(self, db: Session):
        self.db = db

    def validate_catalog(self, system_id: int | None, module_id: int | None = None) -> None:
        if module_id is not None and system_id is None:
            raise AppError(42232, "选择模块前请先选择业务系统", 422)
        if system_id is not None:
            system = self.db.get(BusinessSystem, system_id)
            if system is None or not system.enabled:
                raise AppError(42232, "所属系统不存在或已停用", 422)
        if module_id is not None:
            module = self.db.get(BusinessModule, module_id)
            if module is None or not module.enabled or module.system_id != system_id:
                raise AppError(42233, "模块不存在、已停用或不属于所选系统", 422)

    @staticmethod
    def mismatch(version: Version, requirement: Requirement) -> str | None:
        if version.system_id is None:
            return "版本尚未指定业务系统，请先编辑版本补齐"  # noqa: RUF001
        if requirement.system_id is None:
            return "需求尚未指定业务系统，请先编辑需求补齐"  # noqa: RUF001
        if version.system_id != requirement.system_id:
            return "需求与版本不属于同一业务系统"
        return None

    def ensure_match(
        self, version: Version, requirement: Requirement, *, attaching: bool = False
    ) -> None:
        reason = self.mismatch(version, requirement)
        if reason:
            raise AppError(40975, reason, 409)
        if attaching:
            self.validate_catalog(version.system_id)

    def validate_requirement_change(self, item: Requirement, system_id: int | None) -> None:
        if item.status == "ONLINE":
            raise AppError(40975, "已上线需求不能修改业务系统", 409)
        # WorkflowService.lock already holds the version then requirement lock.
        version = (
            self.db.get(Version, item.current_version_id, populate_existing=True)
            if item.current_version_id
            else None
        )
        if version is not None and version.system_id is not None and version.system_id != system_id:
            raise AppError(40975, "修改后的系统与当前版本不一致，请先移出版本", 409)  # noqa: RUF001

    def validate_version_change(self, version: Version, system_id: int) -> None:
        if version.release_frozen or self.db.scalar(
            select(ReleaseBatch.id)
            .where(
                ReleaseBatch.version_id == version.id,
                ReleaseBatch.kind == "INITIAL",
                ReleaseBatch.status != "CANCELED",
            )
            .limit(1)
        ):
            raise AppError(40986, "已有首次发布计划, 请先处理该计划, 不能更改业务系统", 409)
        if version.status in {"RELEASED", "CANCELED"}:
            raise AppError(40975, "终态版本不能修改业务系统", 409)
        self.validate_catalog(system_id)
        # Caller holds the version lock; all relationship writers use that lock.
        items = self.db.scalars(
            select(Requirement)
            .join(VersionRequirement, VersionRequirement.requirement_id == Requirement.id)
            .where(VersionRequirement.version_id == version.id, VersionRequirement.active.is_(True))
            .order_by(Requirement.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        if any(item.system_id != system_id for item in items):
            # Do not disclose out-of-scope requirement identities.
            raise AppError(40975, "版本包含系统未补齐或不一致的需求，请先处理需求清单", 409)  # noqa: RUF001

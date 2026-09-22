from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import (
    ManualRequirementStatus,
    RequirementSource,
    RequirementStatus,
    VersionStatus,
)
from app.repositories.requirement_repository import RequirementRepository
from app.schemas.requirement import (
    RequirementCreate,
    RequirementStatusChange,
    RequirementUpdate,
)
from app.services.audit_service import AuditService

ALLOWED_TRANSITIONS: dict[RequirementStatus, set[ManualRequirementStatus]] = {
    RequirementStatus.DRAFT: {
        ManualRequirementStatus.CONFIRMED,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.CONFIRMED: {
        ManualRequirementStatus.PLANNED,
        ManualRequirementStatus.PAUSED,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.PLANNED: {
        ManualRequirementStatus.DEVELOPING,
        ManualRequirementStatus.PAUSED,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.DEVELOPING: {
        ManualRequirementStatus.TESTING,
        ManualRequirementStatus.PAUSED,
    },
    RequirementStatus.TESTING: {
        ManualRequirementStatus.DEVELOPING,
        ManualRequirementStatus.DONE,
        ManualRequirementStatus.PAUSED,
    },
    RequirementStatus.DONE: {ManualRequirementStatus.DEVELOPING},
    RequirementStatus.PAUSED: {
        ManualRequirementStatus.CONFIRMED,
        ManualRequirementStatus.PLANNED,
        ManualRequirementStatus.DEVELOPING,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.ONLINE: set(),
    RequirementStatus.CANCELED: set(),
}


class RequirementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RequirementRepository(db)
        self.audit = AuditService(db)

    def create(
        self,
        payload: RequirementCreate,
        operator_id: int,
        source: RequirementSource = RequirementSource.DIRECT,
    ) -> Requirement:
        if payload.version_id is not None:
            target_version = self.db.scalar(
                select(Version).where(Version.id == payload.version_id).with_for_update()
            )
            if target_version is None:
                raise NotFoundError("目标版本不存在")
            if target_version.status in {VersionStatus.RELEASED, VersionStatus.CANCELED}:
                raise ConflictError("不能将需求加入已发布或已取消版本")
        item = Requirement(
            requirement_no=next_business_no(
                self.db, Requirement, Requirement.requirement_no, "REQ"
            ),
            source=source,
            created_by=operator_id,
            updated_by=operator_id,
            **payload.model_dump(exclude={"version_id"}),
        )
        self.db.add(item)
        self.db.flush()
        if payload.version_id:
            self.db.add(
                VersionRequirement(
                    version_id=payload.version_id, requirement_id=item.id, added_by=operator_id
                )
            )
            item.current_version_id = payload.version_id
            item.status = RequirementStatus.PLANNED
        self.audit.log(
            "REQUIREMENT",
            item.id,
            "CREATE",
            after={"requirement_no": item.requirement_no},
        )
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(
        self, requirement_id: int, payload: RequirementUpdate, operator_id: int
    ) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        values = payload.model_dump(exclude_unset=True, exclude={"revision"}) | {
            "updated_by": operator_id
        }
        # Snapshot the real old values of the changed business fields before the
        # atomic UPDATE mutates this in-session object (synchronize_session).
        changed_fields = [key for key in values if key != "updated_by"]
        before_values = {key: getattr(current, key) for key in changed_fields}
        after_values = {key: values[key] for key in changed_fields}
        if not self.repo.update_with_revision(requirement_id, payload.revision, values):
            latest = self.repo.get(requirement_id)
            raise ConflictError(
                "该需求已被其他用户修改，请刷新后重试",  # noqa: RUF001
                {
                    "current_revision": latest.revision if latest else None,
                    "current_updated_at": latest.updated_at.isoformat() if latest else None,
                    "current_updated_by": latest.updated_by if latest else None,
                },
            )
        self.audit.log(
            "REQUIREMENT",
            requirement_id,
            "UPDATE",
            before=before_values,
            after=after_values,
        )
        self.db.commit()
        updated = self.repo.get(requirement_id)
        assert updated is not None
        return updated

    def change_status(
        self, requirement_id: int, payload: RequirementStatusChange, operator_id: int
    ) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        current_status = RequirementStatus(current.status)
        # Capture before the atomic UPDATE mutates the in-session object.
        previous_status = current.status
        if payload.status not in ALLOWED_TRANSITIONS[current_status]:
            raise AppError(40911, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if (
            current.status == RequirementStatus.DONE
            and payload.status == ManualRequirementStatus.DEVELOPING
        ):
            if not payload.reason or not payload.reason.strip():
                raise AppError(42211, "DONE 退回 DEVELOPING 必须填写原因", 422)
            if current.current_version_id is not None:
                version_status = self.db.scalar(
                    select(Version.status)
                    .where(Version.id == current.current_version_id)
                    .with_for_update()
                )
                if version_status == VersionStatus.RELEASED:
                    raise AppError(40912, "已发布版本中的需求不能退回开发中", 409)
        if not self.repo.update_with_revision(
            requirement_id,
            payload.revision,
            {
                "status": RequirementStatus(payload.status.value),
                "updated_by": operator_id,
            },
        ):
            raise ConflictError("需求状态已被其他用户修改")
        self.audit.log(
            "REQUIREMENT",
            requirement_id,
            "STATUS_CHANGE",
            before={"status": previous_status},
            after={"status": payload.status, "reason": payload.reason},
        )
        self.db.commit()
        updated = self.repo.get(requirement_id)
        assert updated is not None
        return updated

    # NOTE: moving a requirement between versions now lives in VersionService
    # (POST /versions/{id}/requirements/move). All version<->requirement changes
    # go through VersionService so freeze rules + the active-relation invariant
    # are enforced in one place.

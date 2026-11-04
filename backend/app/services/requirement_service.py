from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import Requirement, RequirementParticipant, Version
from app.models.enums import (
    DataScope,
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
from app.services.collaboration_service import CollaborationService
from app.services.revision_conflict import revision_conflict_data
from app.services.rich_text import sanitize_requirement_description
from app.services.workflow_service import WorkflowService

ALLOWED_TRANSITIONS: dict[RequirementStatus, set[ManualRequirementStatus]] = {
    RequirementStatus.DRAFT: {
        ManualRequirementStatus.CONFIRMED,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.CONFIRMED: {
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
        *,
        viewer_scope: DataScope,
    ) -> Requirement:
        item = Requirement(
            requirement_no=next_business_no(
                self.db, Requirement, Requirement.requirement_no, "REQ"
            ),
            source=source,
            created_by=operator_id,
            updated_by=operator_id,
            **payload.model_dump(
                exclude={"version_id", "version_revision", "participants", "owner_id"}
            ),
        )
        collaboration = CollaborationService(self.db)
        collaboration.validate_people(
            sorted({p.user_id for p in payload.participants}), "requirement", operator_id
        )
        self.db.add(item)
        self.db.flush()
        for person in payload.participants:
            self.db.add(RequirementParticipant(requirement_id=item.id, **person.model_dump()))
        self.db.flush()
        if payload.version_id is not None:
            # Keep the VersionRequirement relation authoritative and route every
            # relation mutation through VersionService. The creation transaction
            # remains atomic: VersionService only flushes here; this method owns
            # the commit together with the Requirement CREATE audit.
            from app.services.version_service import VersionService

            VersionService(self.db).attach_new_requirement(
                payload.version_id,
                item,
                version_revision=payload.version_revision,
                operator_id=operator_id,
                viewer_scope=viewer_scope,
            )
        self.audit.log(
            "REQUIREMENT",
            item.id,
            "CREATE",
            after={"requirement_no": item.requirement_no},
        )
        collaboration.requirement_event(item, "CREATED", operator_id)
        self.db.commit()
        self.db.refresh(item)
        self.repo.populate_handlers([item])
        return item

    def update(
        self, requirement_id: int, payload: RequirementUpdate, operator_id: int
    ) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        WorkflowService(self.db).lock(current)
        values = payload.model_dump(exclude_unset=True, exclude={"revision", "owner_id"}) | {
            "updated_by": operator_id
        }
        if "description" in values or "description_format" in values:
            try:
                values["description"] = sanitize_requirement_description(
                    values.get("description", current.description),
                    values.get("description_format", current.description_format),
                )
            except ValueError as exc:
                raise AppError(42265, str(exc), 422) from exc
        content_changed = any(
            key in values and values[key] != getattr(current, key)
            for key in ("description", "description_format", "acceptance_criteria")
        )
        if content_changed:
            if current.status == RequirementStatus.ONLINE:
                raise AppError(40961, "已上线需求范围不可修改", 409)
            values["content_revision"] = current.content_revision + 1
            values["legacy_completed"] = False
        # Snapshot the real old values of the changed business fields before the
        # atomic UPDATE mutates this in-session object (synchronize_session).
        changed_fields = [key for key in values if key != "updated_by"]
        before_values = {key: getattr(current, key) for key in changed_fields}
        after_values = {key: values[key] for key in changed_fields}
        if not self.repo.update_with_revision(requirement_id, payload.revision, values):
            self.db.expire_all()
            latest = self.repo.get(requirement_id)
            raise ConflictError(
                "该需求已被其他用户修改，请刷新后重试",  # noqa: RUF001
                revision_conflict_data(latest),
            )
        self.audit.log(
            "REQUIREMENT",
            requirement_id,
            "UPDATE",
            before=before_values,
            after=after_values,
        )
        if content_changed:
            self.db.flush()
            CollaborationService(self.db).requirement_event(current, "RECONFIRM", operator_id)
        self.db.commit()
        updated = self.repo.get(requirement_id)
        assert updated is not None
        self.repo.populate_handlers([updated])
        return updated

    def change_status(
        self, requirement_id: int, payload: RequirementStatusChange, operator_id: int
    ) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        workflow = WorkflowService(self.db)
        workflow.lock(current)
        if current.revision != payload.revision:
            raise ConflictError("需求状态已被其他用户修改", revision_conflict_data(current))
        current_status = RequirementStatus(current.status)
        # Capture before the atomic UPDATE mutates the in-session object.
        previous_status = current.status
        if payload.status not in ALLOWED_TRANSITIONS[current_status]:
            raise AppError(40911, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        workflow_values: dict[str, Any] = {}
        if (
            current.status == RequirementStatus.DRAFT
            and payload.status == ManualRequirementStatus.CONFIRMED
        ):
            workflow_values["confirmed_revision"] = current.content_revision
        if payload.status == ManualRequirementStatus.PAUSED:
            workflow_values["paused_from"] = current.status
        if (
            current.status == RequirementStatus.DONE
            and payload.status == ManualRequirementStatus.DEVELOPING
        ):
            workflow_values["legacy_completed"] = False
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
        workflow.validate_transition(current, payload.status, operator_id, payload.reason)
        if not self.repo.update_with_revision(
            requirement_id,
            payload.revision,
            {
                "status": RequirementStatus(payload.status.value),
                **workflow_values,
                "updated_by": operator_id,
            },
        ):
            self.db.expire_all()
            raise ConflictError(
                "需求状态已被其他用户修改",
                revision_conflict_data(self.repo.get(requirement_id)),
            )
        workflow.record(
            current,
            f"STATUS_{payload.status}",
            operator_id,
            {"from": previous_status, "to": payload.status, "reason": payload.reason},
        )
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
        self.repo.populate_handlers([updated])
        return updated

    # NOTE: moving a requirement between versions now lives in VersionService
    # (POST /versions/{id}/requirements/move). All version<->requirement changes
    # go through VersionService so freeze rules + the active-relation invariant
    # are enforced in one place.

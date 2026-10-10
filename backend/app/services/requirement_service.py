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
    RequirementStageStart,
    RequirementStatusChange,
    RequirementUpdate,
)
from app.services.audit_service import AuditService
from app.services.requirement_collaboration_service import RequirementCollaborationService
from app.services.revision_conflict import revision_conflict_data

STATUS_LABELS = {
    RequirementStatus.DRAFT: "草稿",
    RequirementStatus.CONFIRMED: "已确认",
    RequirementStatus.PLANNED: "已排期",
    RequirementStatus.DESIGNING: "设计中",
    RequirementStatus.DEVELOPING: "开发中",
    RequirementStatus.TESTING: "测试中",
    RequirementStatus.DONE: "已完成",
    RequirementStatus.ONLINE: "已上线",
    RequirementStatus.PAUSED: "已暂停",
    RequirementStatus.CANCELED: "已取消",
}

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
        ManualRequirementStatus.DESIGNING,
        ManualRequirementStatus.DEVELOPING,
        ManualRequirementStatus.PAUSED,
        ManualRequirementStatus.CANCELED,
    },
    RequirementStatus.DESIGNING: {
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
        ManualRequirementStatus.DESIGNING,
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

    def start_stage(
        self, requirement_id: int, payload: RequirementStageStart, operator_id: int
    ) -> Requirement:
        current = self.db.scalar(
            select(Requirement).where(Requirement.id == requirement_id).with_for_update()
        )
        if current is None:
            raise NotFoundError("需求不存在")
        if current.revision != payload.revision:
            raise ConflictError("需求已被其他用户修改", revision_conflict_data(current))
        allowed = (
            {RequirementStatus.PLANNED}
            if payload.status == "DESIGNING"
            else {RequirementStatus.PLANNED, RequirementStatus.DESIGNING}
        )
        if current.status not in allowed:
            raise ConflictError("当前状态不能开始该阶段")
        kind = "DESIGN" if payload.status == "DESIGNING" else "DEVELOPMENT"
        RequirementCollaborationService(self.db).apply_members(current, kind, payload.user_ids)
        return self.change_status(
            requirement_id,
            RequirementStatusChange(
                revision=payload.revision, status=ManualRequirementStatus(payload.status)
            ),
            operator_id,
        )

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
            **payload.model_dump(exclude={"version_id", "version_revision"}),
        )
        self.db.add(item)
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
        if item.owner_id is not None:
            RequirementCollaborationService(self.db).notify(
                item, operator_id, "已分配", "你已成为该需求的总负责人。"
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
        if "owner_id" in values and before_values["owner_id"] != values["owner_id"]:
            RequirementCollaborationService(self.db).notify(
                current, operator_id, "负责人已更新", "请查看最新负责人分工。"
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
        if current.revision != payload.revision:
            raise ConflictError("需求状态已被其他用户修改", revision_conflict_data(current))
        current_status = RequirementStatus(current.status)
        # Capture before the atomic UPDATE mutates the in-session object.
        previous_status = current.status
        if payload.status not in ALLOWED_TRANSITIONS[current_status]:
            raise AppError(40911, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if payload.status == ManualRequirementStatus.DESIGNING or (
            current_status == RequirementStatus.DESIGNING
            and payload.status == ManualRequirementStatus.DEVELOPING
        ):
            kind = (
                "DESIGN" if payload.status == ManualRequirementStatus.DESIGNING else "DEVELOPMENT"
            )
            if (
                self.db.scalar(
                    select(RequirementParticipant.user_id)
                    .where(
                        RequirementParticipant.requirement_id == requirement_id,
                        RequirementParticipant.discipline == kind,
                    )
                    .limit(1)
                )
                is None
            ):
                raise ConflictError("请先选择阶段人员再开始该阶段")
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
            self.db.expire_all()
            raise ConflictError(
                "需求状态已被其他用户修改",
                revision_conflict_data(self.repo.get(requirement_id)),
            )
        self.audit.log(
            "REQUIREMENT",
            requirement_id,
            "STATUS_CHANGE",
            before={"status": previous_status},
            after={"status": payload.status, "reason": payload.reason},
        )
        RequirementCollaborationService(self.db).notify(
            current,
            operator_id,
            "状态已更新",
            f"{STATUS_LABELS[RequirementStatus(previous_status)]} → "
            f"{STATUS_LABELS[RequirementStatus(payload.status.value)]}。请查看需求详情。",
            discipline=(
                "DESIGN"
                if payload.status == ManualRequirementStatus.DESIGNING
                else "DEVELOPMENT"
                if payload.status
                in {ManualRequirementStatus.DEVELOPING, ManualRequirementStatus.TESTING}
                else None
            ),
        )
        self.db.commit()
        updated = self.repo.get(requirement_id)
        assert updated is not None
        return updated

    # NOTE: moving a requirement between versions now lives in VersionService
    # (POST /versions/{id}/requirements/move). All version<->requirement changes
    # go through VersionService so freeze rules + the active-relation invariant
    # are enforced in one place.

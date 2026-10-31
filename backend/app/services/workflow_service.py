from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, PermissionDenied
from app.models.entities import Requirement, RequirementParticipant, RequirementStep, User, Version
from app.models.enums import UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.workflow import DesignStatus, WorkflowAction, WorkflowOut, WorkflowRecord
from app.services.collaboration_service import CollaborationService


class WorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.collaboration = CollaborationService(db)

    def lock(self, item: Requirement):
        version_id = item.current_version_id
        if version_id is not None:
            self.db.execute(select(Version.id).where(Version.id == version_id).with_for_update())
        self.db.refresh(item, with_for_update=True)
        if item.current_version_id != version_id:
            raise ConflictError("需求版本归属已改变, 请刷新后重试")

    def people(self, item: Requirement, role: str | None = None):
        query = (
            select(RequirementParticipant.user_id)
            .join(User)
            .where(
                RequirementParticipant.requirement_id == item.id,
                RequirementParticipant.active.is_(True),
                User.status == UserStatus.ACTIVE,
            )
        )
        if role is not None:
            query = query.where(RequirementParticipant.role == role)
        return list(self.db.scalars(query))

    def actor(self, item: Requirement, role: str, actor_id: int, reason: str | None):
        people = self.people(item, role)
        if not people:
            raise AppError(40961, "请先分配对应环节人员", 409)
        if actor_id not in people:
            if (
                not UserRepository(self.db).can_view_api_docs(actor_id)
                or not reason
                or not reason.strip()
            ):
                raise PermissionDenied("仅对应环节人员可操作; 管理员代操作须填写原因")

    @staticmethod
    def confirmed(item: Requirement):
        return item.legacy_completed or item.confirmed_revision == item.content_revision

    def record(self, item: Requirement, action: str, actor_id: int, detail: dict):
        actor = self.db.get(User, actor_id)
        self.db.add(
            RequirementStep(
                requirement_id=item.id,
                action=action,
                actor_id=actor_id,
                detail={
                    "content_revision": item.content_revision,
                    "actor_name": actor.display_name if actor else None,
                    "description": item.description,
                    "acceptance_criteria": item.acceptance_criteria,
                    "participants": [
                        p.model_dump()
                        for p in self.collaboration.participants_view(item).participants
                    ],
                    **detail,
                },
            )
        )
        self.collaboration.requirement_event(
            item, action, actor_id, follow_feedback=action.startswith("STATUS_")
        )

    def validate_transition(
        self, item: Requirement, target: str, actor_id: int, reason: str | None
    ):
        if target == "CONFIRMED" and item.status == "DRAFT":
            self.actor(item, "CONFIRM", actor_id, reason)
        elif target == "DEVELOPING":
            self.actor(item, "ACCEPT" if item.status == "TESTING" else "DEVELOP", actor_id, reason)
        elif target == "TESTING":
            self.actor(item, "DEVELOP", actor_id, reason)
            if not self.people(item, "ACCEPT"):
                raise AppError(40961, "请先指定验收人", 409)
            if item.design_status not in {"NOT_REQUIRED", "DONE"}:
                raise AppError(40961, "请先完成设计或说明取消设计的原因", 409)
        elif target == "DONE":
            self.actor(item, "ACCEPT", actor_id, reason)
        if target in {"DEVELOPING", "TESTING", "DONE"} and not self.confirmed(item):
            raise AppError(40961, "当前内容尚未确认", 409)
        if (
            target in {"PAUSED", "CANCELED"}
            or item.status == "PAUSED"
            or (item.status in {"TESTING", "DONE"} and target == "DEVELOPING")
        ):
            if not reason or not reason.strip():
                raise AppError(42261, "退回、暂停、恢复或取消必须填写原因", 422)

    def view(self, item: Requirement):
        records = self.db.scalars(
            select(RequirementStep)
            .where(RequirementStep.requirement_id == item.id)
            .order_by(RequirementStep.created_at.desc(), RequirementStep.id)
            .limit(100)
        )
        return WorkflowOut(
            revision=item.revision,
            content_revision=item.content_revision,
            confirmed_revision=item.confirmed_revision,
            needs_confirmation=not self.confirmed(item),
            legacy_completed=item.legacy_completed,
            design_status=cast(DesignStatus, item.design_status),
            paused_from=item.paused_from,
            records=[
                WorkflowRecord(
                    id=r.id,
                    action=r.action,
                    actor_id=r.actor_id,
                    created_at=r.created_at,
                    detail=r.detail,
                )
                for r in records
            ],
        )

    def act(self, item: Requirement, payload: WorkflowAction, actor_id: int):
        self.lock(item)
        if item.status in {"ONLINE", "CANCELED"}:
            raise AppError(40961, "终态需求不能修改流程", 409)
        values: dict[str, Any] = {}
        if payload.action == "REQUEST_CHANGES":
            if item.status != "DRAFT" or not payload.reason or not payload.reason.strip():
                raise AppError(40961, "仅待确认阶段可要求补充, 请填写意见", 409)
            self.actor(item, "CONFIRM", actor_id, payload.reason)
        elif payload.action == "CONFIRM":
            self.actor(item, "CONFIRM", actor_id, payload.reason)
            if item.confirmed_revision == item.content_revision:
                raise AppError(40961, "当前内容已确认", 409)
            values["confirmed_revision"] = item.content_revision
            if item.status == "DRAFT":
                values["status"] = "CONFIRMED"
        else:
            if item.status not in {"CONFIRMED", "DEVELOPING"}:
                raise AppError(40961, "仅待开发或开发中可调整设计", 409)
            self.actor(item, "DESIGN", actor_id, payload.reason)
            targets = {
                "DESIGN_PENDING": "PENDING",
                "DESIGN_START": "IN_PROGRESS",
                "DESIGN_DONE": "DONE",
                "DESIGN_CANCEL": "NOT_REQUIRED",
            }
            target = targets[payload.action]
            allowed = {
                "NOT_REQUIRED": {"PENDING"},
                "PENDING": {"IN_PROGRESS", "NOT_REQUIRED"},
                "IN_PROGRESS": {"DONE", "NOT_REQUIRED"},
                "DONE": {"PENDING", "NOT_REQUIRED"},
            }
            if target not in allowed[item.design_status]:
                raise AppError(40961, "非法设计进度流转", 409)
            if target == "NOT_REQUIRED" or item.design_status == "DONE":
                if not payload.reason or not payload.reason.strip():
                    raise AppError(42261, "取消或重新打开设计必须填写原因", 422)
            values["design_status"] = target
        self.collaboration.bump(item, payload.revision, actor_id, values)
        self.record(
            item,
            payload.action,
            actor_id,
            {
                "reason": payload.reason,
                "description": item.description,
                "acceptance_criteria": item.acceptance_criteria,
            },
        )
        from app.services.audit_service import AuditService

        AuditService(self.db).log(
            "REQUIREMENT", item.id, payload.action, after={**values, "reason": payload.reason}
        )
        self.db.commit()
        return self.view(item)

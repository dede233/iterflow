from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, PermissionDenied
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    FeedbackRecipient,
    Permission,
    Requirement,
    RequirementFeedback,
    RequirementParticipant,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import DataScope, UserStatus
from app.repositories.base import BaseRepository
from app.repositories.user_repository import UserRepository
from app.schemas.collaboration import (
    FeedbackCollaborationOut,
    ParticipantOut,
    ParticipantsChange,
    ParticipantsOut,
    PersonOption,
    PersonPage,
)
from app.services.audit_service import AuditService
from app.services.revision_conflict import revision_conflict_data


class CollaborationService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    @staticmethod
    def _permission(code: str):
        return (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(Role.enabled.is_(True), Permission.code.in_([code, "*"]))
        )

    def eligible_query(self, kind: str, submitter_id: int):
        criteria = [
            User.status == UserStatus.ACTIVE,
            User.id.in_(self._permission(f"rd.{kind}.view")),
        ]
        if kind == "feedback":
            all_scope = (
                select(UserRole.user_id)
                .join(Role)
                .where(Role.enabled.is_(True), Role.data_scope == DataScope.ALL)
            )
            criteria.append(or_(User.id == submitter_id, User.id.in_(all_scope)))
        return select(User).where(*criteria)

    def people(self, kind: str, submitter_id: int, keyword: str, page: int, page_size: int):
        query = self.eligible_query(kind, submitter_id)
        if keyword.strip():
            query = query.where(User.display_name.contains(keyword.strip(), autoescape=True))
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        people = self.db.scalars(
            query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        )
        return PersonPage(
            items=[PersonOption(id=p.id, display_name=p.display_name) for p in people],
            total=total,
            page=page,
            page_size=page_size,
        )

    def validate_people(self, ids: list[int], kind: str, submitter_id: int):
        if len(set(ids)) != len(ids) or any(uid <= 0 for uid in ids):
            raise AppError(42260, "人员不能重复且 ID 必须为正整数", 422)
        eligible = set(
            self.db.scalars(
                self.eligible_query(kind, submitter_id)
                .with_only_columns(User.id)
                .where(User.id.in_(ids))
            )
        )
        if eligible != set(ids):
            raise AppError(42260, "所选人员不存在、已停用或没有读取资格", 422)

    def event(
        self, entity_type: str, entity_id: int, action: str, actor_id: int, recipients: list[int]
    ):
        self.db.add(
            CollaborationEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_id=actor_id,
                recipient_ids=sorted(set(recipients)),
            )
        )

    def requirement_event(
        self, item: Requirement, action: str, actor_id: int, *, follow_feedback: bool = False
    ):
        ids = list(
            self.db.scalars(
                select(RequirementParticipant.user_id).where(
                    RequirementParticipant.requirement_id == item.id,
                    RequirementParticipant.active.is_(True),
                )
            )
        )
        ids.extend([item.created_by] if item.created_by else [])
        if item.current_version_id:
            version = self.db.get(Version, item.current_version_id)
            if (
                version
                and version.owner_id
                and action in {"STATUS_DONE", "RELATION_CHANGE", "PUBLISHED"}
            ):
                ids.append(version.owner_id)
        self.event("REQUIREMENT", item.id, action, actor_id, ids)
        if follow_feedback:
            for feedback in self.db.scalars(
                select(Feedback)
                .join(RequirementFeedback, RequirementFeedback.feedback_id == Feedback.id)
                .where(RequirementFeedback.requirement_id == item.id)
            ):
                self.event(
                    "FEEDBACK",
                    feedback.id,
                    "REQUIREMENT_" + action,
                    actor_id,
                    [feedback.submitter_id, *self.recipient_ids(feedback.id)],
                )

    def recipient_ids(self, feedback_id: int):
        return list(
            self.db.scalars(
                select(FeedbackRecipient.user_id).where(
                    FeedbackRecipient.feedback_id == feedback_id, FeedbackRecipient.active.is_(True)
                )
            )
        )

    def set_recipients(self, item: Feedback, ids: list[int], actor_id: int):
        self.validate_people(ids, "feedback", item.submitter_id)
        if item.handler_id is not None and item.handler_id not in ids:
            raise AppError(40960, "请先转交处理人, 再移除接收人", 409)
        before = self.recipient_ids(item.id)
        self.db.execute(
            update(FeedbackRecipient)
            .where(FeedbackRecipient.feedback_id == item.id)
            .values(active=False)
        )
        for uid in ids:
            row = self.db.get(FeedbackRecipient, (item.id, uid))
            if row:
                row.active = True
            else:
                self.db.add(FeedbackRecipient(feedback_id=item.id, user_id=uid))
        self.db.flush()
        AuditService(self.db).log(
            "FEEDBACK",
            item.id,
            "RECIPIENTS_CHANGE",
            before={"recipient_ids": before},
            after={"recipient_ids": ids},
        )
        self.event("FEEDBACK", item.id, "RECIPIENT_ADDED", actor_id, list(set(ids) - set(before)))

    def feedback_view(self, item: Feedback):
        people = self.db.scalars(
            select(User)
            .join(FeedbackRecipient)
            .where(FeedbackRecipient.feedback_id == item.id, FeedbackRecipient.active.is_(True))
            .order_by(User.id)
        )
        return FeedbackCollaborationOut(
            revision=item.revision,
            recipients=[PersonOption(id=p.id, display_name=p.display_name) for p in people],
            handler_id=item.handler_id,
            accepted_by=item.accepted_by,
            accepted_at=item.accepted_at,
        )

    def bump(self, item: Feedback | Requirement, revision: int, actor_id: int, values=None):
        if not BaseRepository(self.db, type(item)).update_with_revision(
            item.id, revision, {"updated_by": actor_id, **(values or {})}
        ):
            self.db.rollback()
            self.db.refresh(item)
            raise ConflictError("记录已被其他用户修改", revision_conflict_data(item))
        self.db.refresh(item)

    def change_recipients(self, item: Feedback, ids: list[int], revision: int, actor_id: int):
        self.validate_people(ids, "feedback", item.submitter_id)
        if item.handler_id is not None and item.handler_id not in ids:
            raise AppError(40960, "请先转交处理人, 再移除接收人", 409)
        self.bump(item, revision, actor_id)
        self.set_recipients(item, ids, actor_id)
        self.db.commit()
        return self.feedback_view(item)

    def accept_values(self, item: Feedback, actor_id: int, reason: str | None):
        ids = self.recipient_ids(item.id)
        if ids and actor_id not in ids:
            if not self.users.can_view_api_docs(actor_id) or not reason or not reason.strip():
                raise PermissionDenied("需由接收人受理; 管理员代受理须填写原因")
        # A normal status write cannot bypass recipient access validation.
        self.validate_people([actor_id], "feedback", item.submitter_id)
        return {"accepted_by": actor_id, "handler_id": actor_id, "accepted_at": datetime.now(UTC)}

    def transfer(self, item: Feedback, handler_id: int, revision: int, reason: str, actor_id: int):
        if not reason.strip():
            raise AppError(42260, "转交必须填写原因", 422)
        if item.accepted_by is None:
            raise AppError(40960, "请先确认受理", 409)
        self.validate_people([handler_id], "feedback", item.submitter_id)
        if handler_id not in self.recipient_ids(item.id):
            raise AppError(42260, "处理人必须是当前接收人", 422)
        before = item.handler_id
        self.bump(item, revision, actor_id, {"handler_id": handler_id})
        AuditService(self.db).log(
            "FEEDBACK",
            item.id,
            "HANDLER_TRANSFER",
            before={"handler_id": before},
            after={"handler_id": handler_id, "reason": reason},
        )
        self.event(
            "FEEDBACK",
            item.id,
            "HANDLER_TRANSFER",
            actor_id,
            [
                uid
                for uid in (before, handler_id, item.submitter_id, *self.recipient_ids(item.id))
                if uid is not None
            ],
        )
        self.db.commit()
        return self.feedback_view(item)

    def participants_view(self, item: Requirement):
        rows = self.db.execute(
            select(RequirementParticipant, User)
            .join(User)
            .where(
                RequirementParticipant.requirement_id == item.id,
                RequirementParticipant.active.is_(True),
            )
            .order_by(RequirementParticipant.role, User.id)
        )
        return ParticipantsOut(
            revision=item.revision,
            participants=[
                ParticipantOut(
                    user_id=u.id,
                    role=p.role,
                    display_name=u.display_name,
                    active=u.status == UserStatus.ACTIVE,
                )
                for p, u in rows
            ],
        )

    def change_participants(self, item: Requirement, payload: ParticipantsChange, actor_id: int):
        if item.status in {"ONLINE", "CANCELED"}:
            raise AppError(40960, "终态需求不能调整环节人员", 409)
        ids = sorted({p.user_id for p in payload.participants})
        self.validate_people(ids, "requirement", actor_id)
        self.bump(item, payload.revision, actor_id)
        before = self.participants_view(item).model_dump()["participants"]
        self.db.execute(
            update(RequirementParticipant)
            .where(RequirementParticipant.requirement_id == item.id)
            .values(active=False)
        )
        for person in payload.participants:
            row = self.db.get(RequirementParticipant, (item.id, person.user_id, person.role))
            if row:
                row.active = True
            else:
                self.db.add(RequirementParticipant(requirement_id=item.id, **person.model_dump()))
        self.db.flush()
        AuditService(self.db).log(
            "REQUIREMENT",
            item.id,
            "PARTICIPANTS_CHANGE",
            before={"participants": before},
            after=payload.model_dump(exclude={"revision"}),
        )
        self.event(
            "REQUIREMENT",
            item.id,
            "PARTICIPANTS_CHANGE",
            actor_id,
            [*ids, *[p["user_id"] for p in before]],
        )
        self.db.commit()
        return self.participants_view(item)

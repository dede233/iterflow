from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models.entities import Requirement, RequirementOnlineFeedback, RequirementStep, User
from app.models.enums import DataScope, RequirementStatus
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.schemas.online_review import (
    OnlineReviewConfirm,
    OnlineReviewConfirmation,
    OnlineReviewFeedbackCreate,
    OnlineReviewFeedbackItem,
    OnlineReviewOut,
)
from app.services.audit_service import AuditService
from app.services.feedback_service import FeedbackService
from app.services.revision_conflict import revision_conflict_data

CONFIRM_ACTION = "ONLINE_EFFECT_CONFIRMED"
FEEDBACK_PAGE_SIZE = 10


class OnlineReviewService:
    def __init__(self, db: Session):
        self.db = db
        self.requirements = RequirementRepository(db)

    def _get_online(
        self, requirement_id: int, user_id: int, scope: DataScope, *, lock: bool = False
    ) -> Requirement:
        item = self.requirements.get_scoped(requirement_id, user_id, scope, lock=lock)
        if item is None:
            raise NotFoundError("需求不存在")
        release_id = (
            self.requirements.successful_release_id(item.id)
            if item.status == RequirementStatus.ONLINE
            else None
        )
        if release_id is None:
            raise ConflictError("需求尚未成功发布上线", code=40987)
        return item

    def _confirmation(self, requirement_id: int) -> RequirementStep | None:
        return self.db.scalar(
            select(RequirementStep).where(
                RequirementStep.requirement_id == requirement_id,
                RequirementStep.action == CONFIRM_ACTION,
            )
        )

    @staticmethod
    def _confirmation_output(step: RequirementStep) -> OnlineReviewConfirmation:
        assert step.actor_id is not None
        return OnlineReviewConfirmation(
            confirmed_by=step.actor_id,
            confirmed_by_name=step.detail["actor_name"],
            confirmed_at=step.created_at,
            note=step.detail["note"],
        )

    def view(
        self,
        requirement_id: int,
        user_id: int,
        scope: DataScope,
        page: int,
        *,
        can_view_feedback: bool,
    ) -> OnlineReviewOut:
        item = self._get_online(requirement_id, user_id, scope)
        step = self._confirmation(item.id)
        items, total = (
            FeedbackRepository(self.db).list_online_for_requirement(
                item.id, user_id, scope, page, FEEDBACK_PAGE_SIZE
            )
            if can_view_feedback
            else ([], 0)
        )
        return OnlineReviewOut(
            revision=item.revision,
            can_confirm=step is None and item.created_by == user_id,
            confirmation=self._confirmation_output(step) if step else None,
            feedbacks=[OnlineReviewFeedbackItem.model_validate(feedback) for feedback in items],
            feedback_total=total,
        )

    def _advance_revision(self, item: Requirement, revision: int, user_id: int) -> None:
        requirement_id = item.id
        if self.requirements.update_with_revision(
            requirement_id, revision, {"updated_by": user_id}
        ):
            return
        self.db.rollback()
        latest = self.requirements.get(requirement_id)
        raise ConflictError("需求已被其他用户修改", revision_conflict_data(latest))

    def confirm(
        self, requirement_id: int, payload: OnlineReviewConfirm, user: User, scope: DataScope
    ) -> OnlineReviewConfirmation:
        try:
            item = self._get_online(requirement_id, user.id, scope, lock=True)
            if item.created_by != user.id:
                raise PermissionDenied("仅需求创建人本人可确认线上效果")
            if item.revision != payload.revision:
                raise ConflictError("需求已被其他用户修改", revision_conflict_data(item))
            if self._confirmation(item.id) is not None:
                raise ConflictError("线上效果已确认", code=40988)
            self._advance_revision(item, payload.revision, user.id)
            note = (payload.note or "").strip() or None
            step = RequirementStep(
                requirement_id=item.id,
                action=CONFIRM_ACTION,
                actor_id=user.id,
                detail={"actor_name": user.display_name, "note": note},
            )
            self.db.add(step)
            AuditService(self.db).log(
                "REQUIREMENT",
                item.id,
                CONFIRM_ACTION,
                after={"note": note},
            )
            self.db.flush()
            output = self._confirmation_output(step)
            self.db.commit()
            return output
        except Exception:
            self.db.rollback()
            raise

    def create_feedback(
        self,
        requirement_id: int,
        payload: OnlineReviewFeedbackCreate,
        user_id: int,
        scope: DataScope,
    ) -> FeedbackOut:
        try:
            item = self._get_online(requirement_id, user_id, scope, lock=True)
            self._advance_revision(item, payload.revision, user_id)
            service = FeedbackService(self.db)
            feedback = service.create(
                FeedbackCreate.model_validate(payload.model_dump(exclude={"revision"})),
                user_id,
                commit=False,
            )
            self.db.add(RequirementOnlineFeedback(requirement_id=item.id, feedback_id=feedback.id))
            AuditService(self.db).log(
                "FEEDBACK", feedback.id, "CREATE_ONLINE_FEEDBACK", after={"requirement_id": item.id}
            )
            output = service.to_output(feedback)
            self.db.commit()
            return output
        except Exception:
            self.db.rollback()
            raise

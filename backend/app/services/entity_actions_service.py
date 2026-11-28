from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.models.entities import (
    Feedback,
    Requirement,
    RequirementFeedback,
    RequirementOnlineFeedback,
    RequirementParticipant,
    User,
    VersionRequirement,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    ManualFeedbackStatus,
    ManualRequirementStatus,
    RequirementSource,
    RequirementStatus,
    UserStatus,
)
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.schemas.entity_actions import (
    BatchActionResponse,
    BatchActionResult,
    EntityDelete,
    EntityDeleted,
    FeedbackBatchAction,
    RequirementBatchAction,
)
from app.schemas.feedback import FeedbackStatusChange
from app.schemas.requirement import RequirementStatusChange
from app.schemas.workflow import WorkflowAction
from app.services.audit_service import AuditService
from app.services.feedback_service import FeedbackService
from app.services.requirement_service import RequirementService
from app.services.revision_conflict import revision_conflict_data
from app.services.workflow_service import WorkflowService


class EntityActionsService:
    def __init__(self, db: Session):
        self.db = db

    def _can_delete_as_editor_or_creator(
        self, item: Feedback | Requirement, operator_id: int
    ) -> bool:
        creator_id: int | None
        if isinstance(item, Feedback):
            kind, creator_id = "feedback", item.submitter_id
        else:
            kind, creator_id = "requirement", item.created_by
        codes = UserRepository(self.db).permission_codes(operator_id)
        return not codes.isdisjoint(("*", f"rd.{kind}.edit")) or (
            creator_id == operator_id and f"rd.{kind}.view" in codes
        )

    def _ensure_deletable(self, item: Feedback | Requirement, *, lock: bool) -> None:
        entity_id = item.id
        if isinstance(item, Feedback):
            if item.status != FeedbackStatus.NEW:
                raise AppError(40971, "仅待受理反馈可删除", 409)
            if (
                item.accepted_at is not None
                or item.accepted_by is not None
                or FeedbackRepository(self.db).has_acceptance_history(entity_id, lock=lock)
            ):
                raise AppError(40971, "反馈已有受理记录, 不能删除", 409)
            has_pointer = item.main_requirement_id is not None or item.duplicate_of_id is not None
            checks = (
                select(Feedback.id).where(Feedback.duplicate_of_id == entity_id),
                select(RequirementFeedback.id).where(RequirementFeedback.feedback_id == entity_id),
                select(RequirementOnlineFeedback.feedback_id).where(
                    RequirementOnlineFeedback.feedback_id == entity_id
                ),
            )
        else:
            if item.status != RequirementStatus.DRAFT:
                raise AppError(40971, "仅待确认需求可删除", 409)
            if (
                item.confirmed_revision is not None
                or item.legacy_completed
                or RequirementRepository(self.db).has_confirmation_history(entity_id, lock=lock)
            ):
                raise AppError(40971, "需求已有确认记录, 不能删除", 409)
            has_pointer = (
                item.source != RequirementSource.DIRECT or item.current_version_id is not None
            )
            checks = (
                select(VersionRequirement.id).where(VersionRequirement.requirement_id == entity_id),
                select(RequirementFeedback.id).where(
                    RequirementFeedback.requirement_id == entity_id
                ),
                select(RequirementOnlineFeedback.feedback_id).where(
                    RequirementOnlineFeedback.requirement_id == entity_id
                ),
            )
        if has_pointer:
            raise AppError(40972, "记录已有业务关联或历史引用, 不能删除", 409)
        for query in checks:
            query = query.limit(1)
            if lock:
                query = query.with_for_update()
            if self.db.scalar(query) is not None:
                raise AppError(40972, "记录已有业务关联或历史引用, 不能删除", 409)
        if isinstance(item, Feedback) and FeedbackRepository(self.db).has_duplicate_history(
            entity_id, lock=lock
        ):
            raise AppError(40972, "记录已有业务关联或历史引用, 不能删除", 409)

    def can_delete(self, item: Feedback | Requirement, operator_id: int) -> bool:
        if not self._can_delete_as_editor_or_creator(item, operator_id):
            return False
        try:
            self._ensure_deletable(item, lock=False)
        except AppError:
            return False
        return True

    def delete(
        self,
        kind: Literal["feedback", "requirement"],
        entity_id: int,
        payload: EntityDelete,
        operator_id: int,
    ) -> EntityDeleted:
        scope = UserRepository(self.db).data_scope(operator_id)
        repo = FeedbackRepository(self.db) if kind == "feedback" else RequirementRepository(self.db)
        item = repo.get_scoped(entity_id, operator_id, scope)
        if item is None:
            raise NotFoundError()
        # Relation writers also lock/bump this parent. Read the latest row and
        # relation facts after the lock, including under MySQL REPEATABLE READ.
        if isinstance(item, Requirement):
            WorkflowService(self.db).lock(item)
            if (
                scope is not DataScope.ALL
                and operator_id not in {item.created_by, item.owner_id}
                and self.db.scalar(
                    select(RequirementParticipant.user_id)
                    .where(
                        RequirementParticipant.requirement_id == entity_id,
                        RequirementParticipant.user_id == operator_id,
                        RequirementParticipant.active.is_(True),
                    )
                    .limit(1)
                    .with_for_update()
                )
                is None
            ):
                raise NotFoundError()
        else:
            self.db.refresh(item, with_for_update=True)
        if item.deleted_at is not None:
            raise NotFoundError()
        if not self._can_delete_as_editor_or_creator(item, operator_id):
            raise PermissionDenied()
        if item.revision != payload.revision:
            raise ConflictError("记录已被其他用户修改", revision_conflict_data(item))
        self._ensure_deletable(item, lock=True)
        now = datetime.now(UTC)
        if not repo.update_with_revision(
            entity_id,
            payload.revision,
            {
                "deleted_at": now,
                "deleted_by": operator_id,
                "updated_by": operator_id,
            },
        ):
            raise ConflictError("记录已被其他用户修改")
        AuditService(self.db).log(
            kind.upper(),
            entity_id,
            "SOFT_DELETE",
            before={"status": item.status, "deleted_at": None},
            after={"deleted_at": now.isoformat(), "reason": payload.reason},
        )
        self.db.commit()
        return EntityDeleted(id=entity_id, revision=payload.revision + 1)

    def batch(
        self,
        kind: Literal["feedback", "requirement"],
        payload: FeedbackBatchAction | RequirementBatchAction,
        operator_id: int,
    ) -> BatchActionResponse:
        results: list[BatchActionResult] = []
        for entry in payload.items:
            try:
                # Each single-item service owns its transaction. Recheck identity,
                # permissions and scope for each item; previous successes persist.
                self.db.expire_all()
                user = self.db.get(User, operator_id, populate_existing=True)
                if user is None or user.status != UserStatus.ACTIVE:
                    raise PermissionDenied("账号已不可用")
                users = UserRepository(self.db)
                permission = "rd.feedback.edit" if kind == "feedback" else "rd.requirement.status"
                codes = users.permission_codes(operator_id)
                if "*" not in codes and permission not in codes:
                    raise PermissionDenied()
                scope = users.data_scope(operator_id)
                if kind == "feedback":
                    item = FeedbackRepository(self.db).get_scoped(entry.id, operator_id, scope)
                    if item is None:
                        raise NotFoundError()
                    updated = FeedbackService(self.db).change_status(
                        entry.id,
                        FeedbackStatusChange(
                            status=ManualFeedbackStatus(payload.action),
                            revision=entry.revision,
                            reason=payload.reason,
                        ),
                        operator_id,
                        viewer_scope=scope,
                        viewer_id=operator_id,
                    )
                    revision = updated.revision
                else:
                    requirement = RequirementRepository(self.db).get_scoped(
                        entry.id, operator_id, scope
                    )
                    if requirement is None:
                        raise NotFoundError()
                    source = {
                        "DEVELOPING": "CONFIRMED",
                        "TESTING": "DEVELOPING",
                        "DONE": "TESTING",
                    }.get(payload.action)
                    if source is not None and requirement.status != source:
                        raise AppError(40971, "当前阶段不支持所选批量操作", 409)
                    if payload.action == "CONFIRM":
                        workflow = WorkflowService(self.db).act(
                            requirement,
                            WorkflowAction(
                                action="CONFIRM",
                                revision=entry.revision,
                                reason=payload.reason,
                            ),
                            operator_id,
                        )
                        revision = workflow.revision
                    else:
                        changed = RequirementService(self.db).change_status(
                            entry.id,
                            RequirementStatusChange(
                                status=ManualRequirementStatus(payload.action),
                                revision=entry.revision,
                                reason=payload.reason,
                            ),
                            operator_id,
                        )
                        revision = changed.revision
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=True,
                        status_code=200,
                        code=0,
                        message="操作成功",
                        revision=revision,
                    )
                )
            except AppError as error:
                self.db.rollback()
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=False,
                        status_code=error.status_code,
                        code=error.code,
                        message=error.message,
                        revision=None,
                    )
                )
            except Exception:
                self.db.rollback()
                # Never expose SQL/driver details or credentials in item errors.
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=False,
                        status_code=500,
                        code=50000,
                        message="操作失败, 请刷新核对后重试",
                        revision=None,
                    )
                )
        return BatchActionResponse(results=results)

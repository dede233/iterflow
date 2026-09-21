from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    Feedback,
    Requirement,
    RequirementFeedback,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    ManualFeedbackStatus,
    RequirementSource,
    RequirementStatus,
    VersionStatus,
)
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import (
    FeedbackConvertRequest,
    FeedbackCreate,
    FeedbackStatusChange,
    FeedbackUpdate,
)
from app.services.audit_service import AuditService

# Frozen Feedback state machine (V1.5). Keys are the current status; values are
# the human-settable target statuses. Downstream statuses (REQUIREMENT_LINKED,
# PLANNED, DEVELOPING, TESTING, ONLINE) map to an empty set: they are produced
# only by convert / version / publish transactions and can never be set here.
ALLOWED_TRANSITIONS: dict[FeedbackStatus, set[ManualFeedbackStatus]] = {
    FeedbackStatus.NEW: {
        ManualFeedbackStatus.ACCEPTED,
        ManualFeedbackStatus.DUPLICATE,
        ManualFeedbackStatus.CANNOT_REPRODUCE,
        ManualFeedbackStatus.CLOSED,
    },
    FeedbackStatus.ACCEPTED: {
        ManualFeedbackStatus.DUPLICATE,
        ManualFeedbackStatus.CANNOT_REPRODUCE,
        ManualFeedbackStatus.CLOSED,
    },
    FeedbackStatus.DUPLICATE: {ManualFeedbackStatus.NEW},
    FeedbackStatus.CANNOT_REPRODUCE: {ManualFeedbackStatus.NEW},
    FeedbackStatus.CLOSED: {ManualFeedbackStatus.NEW},
    FeedbackStatus.REQUIREMENT_LINKED: set(),
    FeedbackStatus.PLANNED: set(),
    FeedbackStatus.DEVELOPING: set(),
    FeedbackStatus.TESTING: set(),
    FeedbackStatus.ONLINE: set(),
}

# Targets that require a non-empty reason (trimmed).
_REASON_REQUIRED: set[ManualFeedbackStatus] = {
    ManualFeedbackStatus.CANNOT_REPRODUCE,
    ManualFeedbackStatus.CLOSED,
    ManualFeedbackStatus.NEW,  # reopen
}


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FeedbackRepository(db)
        self.audit = AuditService(db)

    def _validate_system_module(self, system_id: int | None, module_id: int | None) -> None:
        """Validate the effective (system, module) pair for create/edit.

        Both must exist and be enabled, and the module must belong to the system.
        A module can only be set when a system is set.
        """
        if module_id is not None and system_id is None:
            raise AppError(42231, "选择模块时必须同时选择所属系统", 422)
        if system_id is not None:
            system = self.db.get(BusinessSystem, system_id)
            if system is None or not system.enabled:
                raise AppError(42232, "所属系统不存在或已停用", 422, {"system_id": system_id})
        if module_id is not None:
            module = self.db.get(BusinessModule, module_id)
            if module is None or not module.enabled:
                raise AppError(42233, "所属模块不存在或已停用", 422, {"module_id": module_id})
            if module.system_id != system_id:
                raise AppError(42233, "模块不属于所选系统", 422, {"module_id": module_id})

    def create(self, payload: FeedbackCreate, operator_id: int) -> Feedback:
        self._validate_system_module(payload.system_id, payload.module_id)
        item = Feedback(
            feedback_no=next_business_no(self.db, Feedback, Feedback.feedback_no, "FB"),
            submitter_id=operator_id,
            created_by=operator_id,
            updated_by=operator_id,
            **payload.model_dump(),
        )
        self.db.add(item)
        self.db.flush()
        self.audit.log("FEEDBACK", item.id, "CREATE", after={"feedback_no": item.feedback_no})
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, feedback_id: int, payload: FeedbackUpdate, operator_id: int) -> Feedback:
        current = self.repo.get(feedback_id)
        if not current:
            raise NotFoundError("反馈不存在")
        values = payload.model_dump(exclude_unset=True, exclude={"revision"})
        # Validate the resulting (system, module) pair, merging the patch with
        # the stored values so a partial edit can't leave an invalid pairing.
        effective_system = values.get("system_id", current.system_id)
        effective_module = values.get("module_id", current.module_id)
        if "system_id" in values or "module_id" in values:
            self._validate_system_module(effective_system, effective_module)
        values["updated_by"] = operator_id
        if not self.repo.update_with_revision(feedback_id, payload.revision, values):
            latest = self.repo.get(feedback_id)
            if not latest:
                raise NotFoundError("反馈不存在")
            raise ConflictError(
                "该反馈已被其他用户修改",
                {
                    "current_revision": latest.revision,
                    "current_updated_at": latest.updated_at.isoformat(),
                    "current_updated_by": latest.updated_by,
                },
            )
        self.audit.log(
            "FEEDBACK",
            feedback_id,
            "UPDATE",
            before={"revision": payload.revision},
            after=values,
        )
        self.db.commit()
        updated = self.repo.get(feedback_id)
        assert updated is not None
        return updated

    def change_status(
        self,
        feedback_id: int,
        payload: FeedbackStatusChange,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Feedback:
        current = self.repo.get(feedback_id)
        if not current:
            raise NotFoundError("反馈不存在")
        current_status = FeedbackStatus(current.status)
        # Capture the pre-update values now: the atomic UPDATE below runs with
        # synchronize_session, which mutates this in-session object's attributes,
        # so reading them afterwards would return the new state.
        previous_status = current.status
        previous_duplicate_of_id = current.duplicate_of_id
        target = payload.status
        if target not in ALLOWED_TRANSITIONS[current_status]:
            raise AppError(40911, f"不允许从 {current.status} 变更为 {target}", 409)

        if target in _REASON_REQUIRED and (not payload.reason or not payload.reason.strip()):
            raise AppError(42221, f"变更为 {target} 必须填写原因", 422)

        new_duplicate_of_id = current.duplicate_of_id
        if target is ManualFeedbackStatus.DUPLICATE:
            if payload.duplicate_of_id is None:
                raise AppError(42222, "标记重复必须指定 duplicate_of_id", 422)
            if payload.duplicate_of_id == feedback_id:
                raise AppError(42223, "不能把反馈标记为与自身重复", 422)
            target_feedback = self.repo.get_scoped(payload.duplicate_of_id, viewer_id, viewer_scope)
            if target_feedback is None:
                raise AppError(
                    42223,
                    "目标反馈不存在或无权访问",
                    422,
                    {"duplicate_of_id": payload.duplicate_of_id},
                )
            new_duplicate_of_id = payload.duplicate_of_id
        elif target is ManualFeedbackStatus.NEW:
            # Reopen always clears the duplicate link.
            new_duplicate_of_id = None

        values: dict = {
            "status": FeedbackStatus(target.value),
            "duplicate_of_id": new_duplicate_of_id,
            "updated_by": operator_id,
        }
        if not self.repo.update_with_revision(feedback_id, payload.revision, values):
            latest = self.repo.get(feedback_id)
            raise ConflictError(
                "反馈状态已被其他用户修改",
                {
                    "current_revision": latest.revision if latest else None,
                    "current_updated_at": (latest.updated_at.isoformat() if latest else None),
                    "current_updated_by": latest.updated_by if latest else None,
                },
            )
        self.audit.log(
            "FEEDBACK",
            feedback_id,
            "STATUS_CHANGE",
            before={
                "status": previous_status,
                "duplicate_of_id": previous_duplicate_of_id,
            },
            after={
                "status": target,
                "duplicate_of_id": new_duplicate_of_id,
                "reason": payload.reason,
            },
        )
        self.db.commit()
        updated = self.repo.get(feedback_id)
        assert updated is not None
        return updated

    def convert(
        self, feedback_id: int, payload: FeedbackConvertRequest, operator_id: int
    ) -> Requirement:
        feedback = self.repo.get(feedback_id)
        if not feedback:
            raise NotFoundError("反馈不存在")
        if feedback.revision != payload.revision:
            raise ConflictError("反馈已被其他用户修改")
        if feedback.main_requirement_id:
            raise ConflictError("该反馈已经关联正式需求")
        if payload.version_id is not None:
            target_version = self.db.scalar(
                select(Version).where(Version.id == payload.version_id).with_for_update()
            )
            if target_version is None:
                raise NotFoundError("目标版本不存在")
            if target_version.status in {VersionStatus.RELEASED, VersionStatus.CANCELED}:
                raise ConflictError("不能将需求加入已发布或已取消版本")
        req = Requirement(
            requirement_no=next_business_no(
                self.db, Requirement, Requirement.requirement_no, "REQ"
            ),
            title=payload.title,
            requirement_type=payload.requirement_type,
            source=RequirementSource.FEEDBACK,
            priority=payload.priority,
            status=(
                RequirementStatus.PLANNED if payload.version_id else RequirementStatus.CONFIRMED
            ),
            system_id=feedback.system_id,
            module_id=feedback.module_id,
            owner_id=payload.owner_id,
            current_version_id=payload.version_id,
            description=payload.description,
            acceptance_criteria=payload.acceptance_criteria,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(req)
        self.db.flush()
        status = FeedbackStatus.PLANNED if payload.version_id else FeedbackStatus.REQUIREMENT_LINKED
        if not self.repo.update_with_revision(
            feedback_id,
            payload.revision,
            {
                "main_requirement_id": req.id,
                "status": status,
                "updated_by": operator_id,
            },
        ):
            latest = self.repo.get(feedback_id)
            raise ConflictError(
                "反馈已被其他用户修改",
                {"current_revision": latest.revision if latest else None},
            )
        self.db.add(
            RequirementFeedback(
                requirement_id=req.id,
                feedback_id=feedback.id,
                is_primary=True,
            )
        )
        if payload.version_id:
            self.db.add(
                VersionRequirement(
                    version_id=payload.version_id,
                    requirement_id=req.id,
                    added_by=operator_id,
                )
            )
        self.audit.log(
            "FEEDBACK",
            feedback.id,
            "CONVERT_REQUIREMENT",
            after={"requirement_id": req.id},
        )
        self.audit.log(
            "REQUIREMENT",
            req.id,
            "CREATE_FROM_FEEDBACK",
            after={"feedback_id": feedback.id},
        )
        self.db.commit()
        self.db.refresh(req)
        return req

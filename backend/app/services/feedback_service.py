from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import (
    AttachmentRelation,
    BusinessModule,
    BusinessSystem,
    Feedback,
    FileObject,
    Requirement,
    RequirementFeedback,
)
from app.models.enums import (
    DataScope,
    FeedbackConvertType,
    FeedbackStatus,
    ManualFeedbackStatus,
    RequirementSource,
    RequirementStatus,
)
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.schemas.feedback import (
    FeedbackConvertRequest,
    FeedbackCreate,
    FeedbackStatusChange,
    FeedbackUpdate,
)
from app.services.audit_service import AuditService

# Frozen Feedback state machine (V1.5). Keys are the current status; values are
# the human-settable target statuses. Feedback is an external-input record, not
# an R&D workflow: REQUIREMENT_LINKED and ONLINE are the only automated states.
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

    def validate_filter_system_module(self, system_id: int | None, module_id: int | None) -> None:
        """Validate list filter ids: they must exist, but disabled is allowed so
        historical feedback can still be filtered. Unknown ids are 422 (not a
        silent empty result); a module must belong to the given system.
        """
        system = self.db.get(BusinessSystem, system_id) if system_id is not None else None
        if system_id is not None and system is None:
            raise AppError(42234, "筛选的系统不存在", 422, {"system_id": system_id})
        if module_id is not None:
            module = self.db.get(BusinessModule, module_id)
            if module is None:
                raise AppError(42235, "筛选的模块不存在", 422, {"module_id": module_id})
            if system_id is not None and module.system_id != system_id:
                raise AppError(42235, "模块不属于所选系统", 422, {"module_id": module_id})

    # ------------------------------------------------------------------ #
    # Attachments (business relation only stores file_id; never a path).  #
    # Access is authorized by the *feedback* data scope + relation, done  #
    # by the router before calling these methods.                         #
    # ------------------------------------------------------------------ #
    def list_attachment_files(self, feedback_id: int) -> list[FileObject]:
        return list(
            self.db.scalars(
                select(FileObject)
                .join(AttachmentRelation, AttachmentRelation.file_id == FileObject.id)
                .where(
                    AttachmentRelation.entity_type == "FEEDBACK",
                    AttachmentRelation.entity_id == feedback_id,
                )
                .order_by(AttachmentRelation.id.asc())
            ).all()
        )

    def attachment_file(self, feedback_id: int, file_id: int) -> FileObject | None:
        return self.db.scalar(
            select(FileObject)
            .join(AttachmentRelation, AttachmentRelation.file_id == FileObject.id)
            .where(
                AttachmentRelation.entity_type == "FEEDBACK",
                AttachmentRelation.entity_id == feedback_id,
                FileObject.id == file_id,
            )
        )

    def attach_file(self, feedback_id: int, file_id: int, operator_id: int) -> None:
        existing = self.db.scalar(
            select(AttachmentRelation.id).where(
                AttachmentRelation.entity_type == "FEEDBACK",
                AttachmentRelation.entity_id == feedback_id,
                AttachmentRelation.file_id == file_id,
            )
        )
        if existing is None:
            self.db.add(
                AttachmentRelation(file_id=file_id, entity_type="FEEDBACK", entity_id=feedback_id)
            )
        self.audit.log("FEEDBACK", feedback_id, "ATTACHMENT_ADD", after={"file_id": file_id})
        self.db.commit()

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
        # Snapshot the real old values of the fields being changed *before* the
        # atomic UPDATE (synchronize_session mutates this in-session object).
        changed_fields = [key for key in values if key != "updated_by"]
        before_values = {key: getattr(current, key) for key in changed_fields}
        after_values = {key: values[key] for key in changed_fields}
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
            before=before_values,
            after=after_values,
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
        self,
        feedback_id: int,
        payload: FeedbackConvertRequest,
        operator_id: int,
        viewer_scope: DataScope,
        viewer_id: int,
    ) -> Requirement:
        """Convert a feedback to a requirement in a single transaction.

        CREATE_NEW builds a new requirement from the feedback; LINK_EXISTING
        attaches to an existing (scoped-visible) requirement. Either way the
        requirement link + the feedback status flip + the relation row + audit
        all commit together, or nothing does. No version association here.
        """
        feedback = self.repo.get(feedback_id)
        if not feedback:
            raise NotFoundError("反馈不存在")
        if feedback.main_requirement_id is not None:
            raise ConflictError("该反馈已经关联正式需求")
        if feedback.revision != payload.revision:
            raise ConflictError(
                "反馈已被其他用户修改",
                {
                    "current_revision": feedback.revision,
                    "current_updated_at": feedback.updated_at.isoformat(),
                    "current_updated_by": feedback.updated_by,
                },
            )
        previous_status = feedback.status

        if payload.type is FeedbackConvertType.CREATE_NEW:
            target = Requirement(
                requirement_no=next_business_no(
                    self.db, Requirement, Requirement.requirement_no, "REQ"
                ),
                title=payload.requirement_title,
                requirement_type=payload.requirement_type,
                source=RequirementSource.FEEDBACK,
                priority=payload.priority,
                status=RequirementStatus.CONFIRMED,
                system_id=feedback.system_id,
                module_id=feedback.module_id,
                description=payload.description,
                acceptance_criteria=payload.acceptance_criteria,
                created_by=operator_id,
                updated_by=operator_id,
            )
            self.db.add(target)
            self.db.flush()
        else:  # LINK_EXISTING
            requirement_id = payload.requirement_id
            if requirement_id is None:  # defensive; the request validator guarantees this
                raise AppError(42240, "LINK_EXISTING 需要 requirement_id", 422)
            linked = RequirementRepository(self.db).get_scoped(
                requirement_id, viewer_id, viewer_scope
            )
            if linked is None:
                raise NotFoundError("目标需求不存在")
            target = linked

        # Atomic feedback flip; a stale revision here rolls back the whole
        # transaction (including any just-created requirement).
        if not self.repo.update_with_revision(
            feedback_id,
            payload.revision,
            {
                "main_requirement_id": target.id,
                "status": FeedbackStatus.REQUIREMENT_LINKED,
                "updated_by": operator_id,
            },
        ):
            self.db.rollback()
            latest = self.repo.get(feedback_id)
            raise ConflictError(
                "反馈已被其他用户修改",
                {"current_revision": latest.revision if latest else None},
            )
        self.db.add(
            RequirementFeedback(requirement_id=target.id, feedback_id=feedback.id, is_primary=True)
        )
        self.audit.log(
            "FEEDBACK",
            feedback.id,
            "CONVERT_REQUIREMENT",
            before={"status": previous_status},
            after={
                "status": FeedbackStatus.REQUIREMENT_LINKED,
                "requirement_id": target.id,
                "convert_type": payload.type,
            },
        )
        if payload.type is FeedbackConvertType.CREATE_NEW:
            self.audit.log(
                "REQUIREMENT",
                target.id,
                "CREATE_FROM_FEEDBACK",
                after={"feedback_id": feedback.id, "requirement_no": target.requirement_no},
            )
        self.db.commit()
        self.db.refresh(target)
        return target

    def linked_feedbacks(
        self, requirement_id: int, *, viewer_id: int, viewer_scope: DataScope
    ) -> list[tuple[Feedback, bool]]:
        statement = (
            select(Feedback, RequirementFeedback.is_primary)
            .join(RequirementFeedback, RequirementFeedback.feedback_id == Feedback.id)
            .where(RequirementFeedback.requirement_id == requirement_id)
        )
        if viewer_scope is not DataScope.ALL:
            statement = statement.where(Feedback.submitter_id == viewer_id)
        rows = self.db.execute(
            statement.order_by(RequirementFeedback.is_primary.desc(), Feedback.id.asc())
        ).all()
        return [(fb, bool(is_primary)) for fb, is_primary in rows]

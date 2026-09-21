from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import (
    Feedback,
    Requirement,
    RequirementFeedback,
    Version,
    VersionRequirement,
)
from app.models.enums import FeedbackStatus, RequirementSource, RequirementStatus, VersionStatus
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackConvertRequest, FeedbackCreate, FeedbackUpdate
from app.services.audit_service import AuditService


class FeedbackService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FeedbackRepository(db)
        self.audit = AuditService(db)

    def create(self, payload: FeedbackCreate, operator_id: int) -> Feedback:
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
        values = payload.model_dump(exclude_unset=True, exclude={"revision"}) | {
            "updated_by": operator_id
        }
        if not self.repo.update_with_revision(feedback_id, payload.revision, values):
            latest = self.repo.get(feedback_id)
            if not latest:
                raise NotFoundError("反馈不存在")
            raise ConflictError("该反馈已被其他用户修改", {"current_revision": latest.revision})
        self.audit.log("FEEDBACK", feedback_id, "UPDATE", after=values)
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

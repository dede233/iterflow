from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import Version, VersionRequirement, Requirement, Release, RequirementFeedback, Feedback, Notification
from app.repositories.version_repository import VersionRepository
from app.schemas.version import VersionCreate, VersionUpdate, VersionStatusChange, PublishVersionRequest
from app.services.audit_service import AuditService

VERSION_TRANSITIONS = {
    "PLANNING": {"DEVELOPING", "CANCELED"},
    "DEVELOPING": {"TESTING", "CANCELED"},
    "TESTING": {"DEVELOPING", "READY", "CANCELED"},
    "READY": {"TESTING", "RELEASED"},
    "RELEASED": set(),
    "CANCELED": set(),
}


class VersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VersionRepository(db)
        self.audit = AuditService(db)

    def create(self, payload: VersionCreate, operator_id: int) -> Version:
        item = Version(created_by=operator_id, updated_by=operator_id, **payload.model_dump())
        self.db.add(item)
        self.db.flush()
        self.audit.log("VERSION", item.id, "CREATE", operator_id, after={"version_no": item.version_no})
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, version_id: int, payload: VersionUpdate, operator_id: int) -> Version:
        values = payload.model_dump(exclude_none=True, exclude={"revision"}) | {"updated_by": operator_id}
        if not self.repo.update_with_revision(version_id, payload.revision, values):
            latest = self.repo.get(version_id)
            if not latest:
                raise NotFoundError("版本不存在")
            raise ConflictError("版本已被其他用户修改", {"current_revision": latest.revision})
        self.audit.log("VERSION", version_id, "UPDATE", operator_id, after=values)
        self.db.commit()
        return self.repo.get(version_id)

    def change_status(self, version_id: int, payload: VersionStatusChange, operator_id: int) -> Version:
        current = self.repo.get(version_id)
        if not current:
            raise NotFoundError("版本不存在")
        if payload.status not in VERSION_TRANSITIONS.get(current.status, set()):
            raise AppError(40921, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if not self.repo.update_with_revision(version_id, payload.revision, {"status": payload.status, "updated_by": operator_id}):
            raise ConflictError("版本状态已发生变化")
        self.audit.log("VERSION", version_id, "STATUS_CHANGE", operator_id, before={"status": current.status}, after={"status": payload.status})
        self.db.commit()
        return self.repo.get(version_id)

    def publish(self, version_id: int, payload: PublishVersionRequest, operator_id: int) -> Release:
        version = self.repo.get(version_id)
        if not version:
            raise NotFoundError("版本不存在")
        if version.revision != payload.revision:
            raise ConflictError("版本已被其他用户修改")
        if version.status != "READY":
            raise AppError(40922, "只有待发布版本可以执行发布", 409)

        version.status = "RELEASED"
        version.released_at = payload.released_at
        version.updated_by = operator_id
        version.revision += 1
        release = Release(
            version_id=version.id,
            released_at=payload.released_at,
            result=payload.result,
            release_notes=payload.release_notes,
            created_by=operator_id,
            updated_by=operator_id,
        )
        self.db.add(release)

        requirement_ids = self.db.scalars(
            select(VersionRequirement.requirement_id).where(
                VersionRequirement.version_id == version.id,
                VersionRequirement.active.is_(True),
            )
        ).all()
        if requirement_ids:
            done_requirements = self.db.scalars(
                select(Requirement).where(Requirement.id.in_(requirement_ids), Requirement.status == "DONE")
            ).all()
            for req in done_requirements:
                req.status = "ONLINE"
                req.updated_by = operator_id
                req.revision += 1
                feedback_ids = self.db.scalars(
                    select(RequirementFeedback.feedback_id).where(RequirementFeedback.requirement_id == req.id)
                ).all()
                if feedback_ids:
                    fbs = self.db.scalars(select(Feedback).where(Feedback.id.in_(feedback_ids))).all()
                    for fb in fbs:
                        fb.status = "ONLINE"
                        fb.updated_by = operator_id
                        fb.revision += 1
                        self.db.add(Notification(
                            user_id=fb.submitter_id,
                            title=f"反馈 {fb.feedback_no} 已上线",
                            content=f"已随版本 {version.version_no} 发布。",
                            entity_type="FEEDBACK",
                            entity_id=fb.id,
                        ))
        self.audit.log("VERSION", version.id, "PUBLISH", operator_id, after={"result": payload.result})
        self.db.commit()
        self.db.refresh(release)
        return release

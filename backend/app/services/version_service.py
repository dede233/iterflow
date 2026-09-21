from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import (
    Feedback,
    Notification,
    Release,
    Requirement,
    RequirementFeedback,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    FeedbackStatus,
    ManualVersionStatus,
    NotificationType,
    ReleaseResult,
    RequirementStatus,
    VersionStatus,
)
from app.repositories.version_repository import VersionRepository
from app.schemas.version import (
    PublishVersionRequest,
    VersionCreate,
    VersionStatusChange,
    VersionUpdate,
)
from app.services.audit_service import AuditService

VERSION_TRANSITIONS: dict[VersionStatus, set[ManualVersionStatus]] = {
    VersionStatus.PLANNING: {
        ManualVersionStatus.DEVELOPING,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.DEVELOPING: {
        ManualVersionStatus.TESTING,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.TESTING: {
        ManualVersionStatus.DEVELOPING,
        ManualVersionStatus.READY,
        ManualVersionStatus.CANCELED,
    },
    VersionStatus.READY: {ManualVersionStatus.TESTING},
    VersionStatus.RELEASED: set(),
    VersionStatus.CANCELED: set(),
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
        self.audit.log("VERSION", item.id, "CREATE", after={"version_no": item.version_no})
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, version_id: int, payload: VersionUpdate, operator_id: int) -> Version:
        values = payload.model_dump(exclude_unset=True, exclude={"revision"}) | {
            "updated_by": operator_id
        }
        if not self.repo.update_with_revision(version_id, payload.revision, values):
            latest = self.repo.get(version_id)
            if not latest:
                raise NotFoundError("版本不存在")
            raise ConflictError("版本已被其他用户修改", {"current_revision": latest.revision})
        self.audit.log("VERSION", version_id, "UPDATE", after=values)
        self.db.commit()
        updated = self.repo.get(version_id)
        assert updated is not None
        return updated

    def change_status(
        self, version_id: int, payload: VersionStatusChange, operator_id: int
    ) -> Version:
        current = self.repo.get(version_id)
        if not current:
            raise NotFoundError("版本不存在")
        current_status = VersionStatus(current.status)
        if payload.status not in VERSION_TRANSITIONS[current_status]:
            raise AppError(40921, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if (
            current.status == VersionStatus.READY
            and payload.status == ManualVersionStatus.TESTING
            and (not payload.reason or not payload.reason.strip())
        ):
            raise AppError(42222, "READY 退回 TESTING 必须填写原因", 422)
        if not self.repo.update_with_revision(
            version_id,
            payload.revision,
            {"status": VersionStatus(payload.status.value), "updated_by": operator_id},
        ):
            raise ConflictError("版本状态已发生变化")
        self.audit.log(
            "VERSION",
            version_id,
            "STATUS_CHANGE",
            before={"status": current.status},
            after={"status": payload.status, "reason": payload.reason},
        )
        self.db.commit()
        updated = self.repo.get(version_id)
        assert updated is not None
        return updated

    def publish(self, version_id: int, payload: PublishVersionRequest, operator_id: int) -> Release:
        version = self.repo.get(version_id)
        if not version:
            raise NotFoundError("版本不存在")
        if version.status != VersionStatus.READY:
            raise AppError(40922, "只有待发布版本可以执行发布", 409)
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(Version)
                .where(
                    Version.id == version_id,
                    Version.revision == payload.revision,
                    Version.status == VersionStatus.READY,
                )
                .values(
                    status=VersionStatus.RELEASED,
                    released_at=payload.released_at,
                    updated_by=operator_id,
                    revision=Version.revision + 1,
                )
            ),
        )
        if not result.rowcount:
            latest = self.repo.get(version_id)
            raise ConflictError(
                "版本已被其他用户修改",
                {"current_revision": latest.revision if latest else None},
            )
        release = Release(
            version_id=version.id,
            released_at=payload.released_at,
            result=ReleaseResult.SUCCESS,
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
            online_requirement_ids = list(
                self.db.scalars(
                    update(Requirement)
                    .where(
                        Requirement.id.in_(requirement_ids),
                        Requirement.status == RequirementStatus.DONE,
                    )
                    .values(
                        status=RequirementStatus.ONLINE,
                        updated_by=operator_id,
                        revision=Requirement.revision + 1,
                    )
                    .returning(Requirement.id)
                ).all()
            )
            if online_requirement_ids:
                feedback_ids = self.db.scalars(
                    select(RequirementFeedback.feedback_id).where(
                        RequirementFeedback.requirement_id.in_(online_requirement_ids)
                    )
                ).all()
                if feedback_ids:
                    self.db.execute(
                        update(Feedback)
                        .where(Feedback.id.in_(feedback_ids))
                        .values(
                            status=FeedbackStatus.ONLINE,
                            updated_by=operator_id,
                            revision=Feedback.revision + 1,
                        )
                    )
                    feedbacks = self.db.scalars(
                        select(Feedback).where(Feedback.id.in_(feedback_ids))
                    ).all()
                    for feedback in feedbacks:
                        self.db.add(
                            Notification(
                                user_id=feedback.submitter_id,
                                type=NotificationType.FEEDBACK,
                                title=f"反馈 {feedback.feedback_no} 已上线",
                                content=f"已随版本 {version.version_no} 发布。",
                                entity_type="FEEDBACK",
                                entity_id=feedback.id,
                            )
                        )
        self.audit.log(
            "VERSION",
            version.id,
            "PUBLISH",
            after={"result": ReleaseResult.SUCCESS},
        )
        self.db.commit()
        self.db.refresh(release)
        return release

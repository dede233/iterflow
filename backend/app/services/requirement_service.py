from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.ids import next_business_no
from app.models.entities import Requirement, VersionRequirement
from app.repositories.requirement_repository import RequirementRepository
from app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementStatusChange, RequirementMoveVersion
from app.services.audit_service import AuditService

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"CONFIRMED", "CANCELED"},
    "CONFIRMED": {"PLANNED", "PAUSED", "CANCELED"},
    "PLANNED": {"DEVELOPING", "PAUSED", "CANCELED"},
    "DEVELOPING": {"TESTING", "PAUSED"},
    "TESTING": {"DEVELOPING", "DONE", "PAUSED"},
    "DONE": {"ONLINE", "DEVELOPING"},
    "PAUSED": {"CONFIRMED", "PLANNED", "DEVELOPING", "CANCELED"},
    "ONLINE": set(),
    "CANCELED": set(),
}


class RequirementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RequirementRepository(db)
        self.audit = AuditService(db)

    def create(self, payload: RequirementCreate, operator_id: int, source: str = "DIRECT") -> Requirement:
        item = Requirement(
            requirement_no=next_business_no(self.db, Requirement, Requirement.requirement_no, "REQ"),
            source=source,
            created_by=operator_id,
            updated_by=operator_id,
            **payload.model_dump(exclude={"version_id"}),
        )
        self.db.add(item)
        self.db.flush()
        if payload.version_id:
            self.db.add(VersionRequirement(version_id=payload.version_id, requirement_id=item.id, added_by=operator_id))
            item.current_version_id = payload.version_id
            item.status = "PLANNED"
        self.audit.log("REQUIREMENT", item.id, "CREATE", operator_id, after={"requirement_no": item.requirement_no})
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, requirement_id: int, payload: RequirementUpdate, operator_id: int) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        values = payload.model_dump(exclude_none=True, exclude={"revision"}) | {"updated_by": operator_id}
        if not self.repo.update_with_revision(requirement_id, payload.revision, values):
            latest = self.repo.get(requirement_id)
            raise ConflictError("该需求已被其他用户修改，请刷新后重试", {
                "current_revision": latest.revision if latest else None,
                "current_updated_at": latest.updated_at.isoformat() if latest else None,
                "current_updated_by": latest.updated_by if latest else None,
            })
        self.audit.log("REQUIREMENT", requirement_id, "UPDATE", operator_id, before={"revision": payload.revision}, after=values)
        self.db.commit()
        return self.repo.get(requirement_id)

    def change_status(self, requirement_id: int, payload: RequirementStatusChange, operator_id: int) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        if payload.status not in ALLOWED_TRANSITIONS.get(current.status, set()):
            raise AppError(40911, f"不允许从 {current.status} 变更为 {payload.status}", 409)
        if not self.repo.update_with_revision(requirement_id, payload.revision, {"status": payload.status, "updated_by": operator_id}):
            raise ConflictError("需求状态已被其他用户修改")
        self.audit.log("REQUIREMENT", requirement_id, "STATUS_CHANGE", operator_id, before={"status": current.status}, after={"status": payload.status})
        self.db.commit()
        return self.repo.get(requirement_id)

    def move_version(self, requirement_id: int, payload: RequirementMoveVersion, operator_id: int) -> Requirement:
        current = self.repo.get(requirement_id)
        if not current:
            raise NotFoundError("需求不存在")
        if current.revision != payload.revision:
            raise ConflictError("需求已被其他用户更新")
        now = datetime.now(timezone.utc)
        active = self.db.scalar(select(VersionRequirement).where(VersionRequirement.requirement_id == requirement_id, VersionRequirement.active.is_(True)))
        if active:
            active.active = False
            active.removed_at = now
            active.removed_by = operator_id
            active.removed_reason = payload.reason
        self.db.add(VersionRequirement(version_id=payload.target_version_id, requirement_id=requirement_id, added_by=operator_id))
        current.current_version_id = payload.target_version_id
        current.status = "PLANNED" if current.status in {"DRAFT", "CONFIRMED"} else current.status
        current.updated_by = operator_id
        current.revision += 1
        self.audit.log("REQUIREMENT", requirement_id, "MOVE_VERSION", operator_id, before={"version_id": active.version_id if active else None}, after={"version_id": payload.target_version_id, "reason": payload.reason})
        self.db.commit()
        self.db.refresh(current)
        return current

from typing import Literal

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDenied
from app.models.entities import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.audit import AuditOperatorOut, EntityActivityOut

ActivityKind = Literal["feedback", "requirement", "version"]


class EntityActivityService:
    def __init__(self, db: Session):
        self.db = db

    def recent(self, kind: ActivityKind, entity_id: int, user: User) -> list[EntityActivityOut]:
        users = UserRepository(self.db)
        permissions = users.permission_codes(user.id)
        if "*" not in permissions and f"rd.{kind}.view" not in permissions:
            raise PermissionDenied()
        repositories: dict[
            ActivityKind,
            type[FeedbackRepository] | type[RequirementRepository] | type[VersionRepository],
        ] = {
            "feedback": FeedbackRepository,
            "requirement": RequirementRepository,
            "version": VersionRepository,
        }
        repository = repositories[kind](self.db)
        if repository.get_scoped(entity_id, user.id, users.data_scope(user.id)) is None:
            raise NotFoundError("对象不存在")
        rows = AuditRepository(self.db).list_for_entity(kind.upper(), entity_id)
        return [
            EntityActivityOut(
                id=record.id,
                action=record.action,
                operator=(
                    AuditOperatorOut(
                        id=operator.id,
                        username=operator.username,
                        display_name=operator.display_name,
                    )
                    if operator is not None
                    else None
                ),
                created_at=record.created_at,
            )
            for record, operator in rows
        ]

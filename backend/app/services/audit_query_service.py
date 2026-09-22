from datetime import datetime
from typing import ClassVar

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDenied
from app.models.entities import OperationLog, User
from app.models.enums import DataScope
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import UserRepository
from app.schemas.audit import AuditOperatorOut, AuditOut


class AuditQueryService:
    """Authorize and expose existing audit records without mutating them."""

    ENTITY_VIEW_PERMISSIONS: ClassVar[dict[str, str]] = {
        "FEEDBACK": "rd.feedback.view",
        "REQUIREMENT": "rd.requirement.view",
        "VERSION": "rd.version.view",
        "RELEASE": "rd.release.view",
        "USER": "sys.user.view",
        "AUTH": "sys.user.view",
        "ROLE": "sys.role.view",
        "SYSTEM": "sys.system.view",
        "DICTIONARY": "sys.system.view",
    }

    def __init__(self, db: Session):
        self.repo = AuditRepository(db)
        self.user_repo = UserRepository(db)

    def _visible_entity_types(self, user: User) -> tuple[set[str], DataScope]:
        permission_codes = self.user_repo.permission_codes(user.id)
        data_scope = self.user_repo.data_scope(user.id)
        if "*" in permission_codes:
            return set(self.ENTITY_VIEW_PERMISSIONS), data_scope
        return (
            {
                entity_type
                for entity_type, required_permission in self.ENTITY_VIEW_PERMISSIONS.items()
                if required_permission in permission_codes
            },
            data_scope,
        )

    def _validate_entity_filter(self, entity_type: str | None, visible_types: set[str]) -> None:
        if entity_type is None:
            return
        if entity_type not in self.ENTITY_VIEW_PERMISSIONS:
            raise NotFoundError("审计实体类型不存在")
        if entity_type not in visible_types:
            raise PermissionDenied("无权查看该业务对象的审计记录")

    @staticmethod
    def _serialize(item: OperationLog, operator: User | None) -> AuditOut:
        return AuditOut(
            id=item.id,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            action=item.action,
            operator=(
                AuditOperatorOut(
                    id=operator.id,
                    username=operator.username,
                    display_name=operator.display_name,
                )
                if operator is not None
                else None
            ),
            before=item.before_data,
            after=item.after_data,
            created_at=item.created_at,
        )

    def list(
        self,
        user: User,
        *,
        page: int,
        size: int,
        entity_type: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        operator_id: int | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
    ) -> tuple[list[AuditOut], int]:
        visible_types, data_scope = self._visible_entity_types(user)
        self._validate_entity_filter(entity_type, visible_types)
        rows, total = self.repo.list_scoped(
            user_id=user.id,
            data_scope=data_scope,
            entity_types=visible_types,
            page=page,
            size=size,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            operator_id=operator_id,
            time_from=time_from,
            time_to=time_to,
        )
        return [self._serialize(item, operator) for item, operator in rows], total

    def get(self, audit_id: int, user: User) -> AuditOut:
        visible_types, data_scope = self._visible_entity_types(user)
        row = self.repo.get_scoped(
            audit_id,
            user_id=user.id,
            data_scope=data_scope,
            entity_types=visible_types,
        )
        if row is None:
            raise NotFoundError("审计记录不存在")
        return self._serialize(*row)

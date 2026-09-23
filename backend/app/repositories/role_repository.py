from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Permission, Role, RolePermission, UserRole


class RoleRepository:
    """Persistence operations for configurable RBAC roles."""

    def __init__(self, db: Session):
        self.db = db

    def list_roles(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.id)).all())

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def by_code(self, code: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.code == code))

    def permission_ids(self, role_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(RolePermission.permission_id)
                .where(RolePermission.role_id == role_id)
                .order_by(RolePermission.permission_id)
            ).all()
        )

    def existing_permission_ids(self, permission_ids: list[int]) -> set[int]:
        if not permission_ids:
            return set()
        return set(
            self.db.scalars(select(Permission.id).where(Permission.id.in_(permission_ids))).all()
        )

    def list_permissions(self) -> list[Permission]:
        return list(self.db.scalars(select(Permission).order_by(Permission.code)).all())

    def user_count(self, role_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
            )
            or 0
        )

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Permission, Role, RolePermission, User, UserRole
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(db, User)

    def by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def permission_codes(self, user_id: int) -> set[str]:
        rows = self.db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, Role.enabled.is_(True))
        ).all()
        return set(rows)

    def data_scope(self, user_id: int) -> DataScope:
        scopes = self.db.scalars(
            select(Role.data_scope)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.enabled.is_(True))
        ).all()
        parsed = {DataScope(scope) for scope in scopes}
        if DataScope.ALL in parsed:
            return DataScope.ALL
        if DataScope.TEAM in parsed:
            return DataScope.TEAM
        return DataScope.SELF

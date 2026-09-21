from sqlalchemy import func, select
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

    def role_ids(self, user_id: int) -> list[int]:
        return list(
            self.db.scalars(
                select(UserRole.role_id)
                .where(UserRole.user_id == user_id)
                .order_by(UserRole.role_id)
            ).all()
        )

    def role_ids_by_user(self, user_ids: list[int]) -> dict[int, list[int]]:
        if not user_ids:
            return {}
        rows = self.db.execute(
            select(UserRole.user_id, UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
            .order_by(UserRole.user_id, UserRole.role_id)
        ).all()
        role_ids: dict[int, list[int]] = {user_id: [] for user_id in user_ids}
        for user_id, role_id in rows:
            role_ids[user_id].append(role_id)
        return role_ids

    def get_scoped(self, entity_id: int, actor_id: int, data_scope: DataScope) -> User | None:
        statement = select(User).where(User.id == entity_id)
        if data_scope is not DataScope.ALL:
            statement = statement.where(User.id == actor_id)
        return self.db.scalar(statement)

    def list_scoped(
        self,
        actor_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int]:
        criteria = [] if data_scope is DataScope.ALL else [User.id == actor_id]
        total = self.db.scalar(select(func.count()).select_from(User).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(User)
                .where(*criteria)
                .order_by(User.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def data_scope(self, user_id: int) -> DataScope:
        scopes = self.db.scalars(
            select(Role.data_scope)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.enabled.is_(True))
        ).all()
        parsed = {DataScope(scope) for scope in scopes}
        if DataScope.TEAM in parsed:
            raise RuntimeError("TEAM data scope is reserved and unsupported in V1.5")
        if DataScope.ALL in parsed:
            return DataScope.ALL
        return DataScope.SELF

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Requirement
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, db: Session):
        super().__init__(db, Requirement)

    @staticmethod
    def _self_criterion(user_id: int):
        return or_(Requirement.owner_id == user_id, Requirement.created_by == user_id)

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Requirement | None:
        stmt = select(Requirement).where(Requirement.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(self._self_criterion(user_id))
        return self.db.scalar(stmt)

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Requirement], int]:
        criteria = [] if data_scope is DataScope.ALL else [self._self_criterion(user_id)]
        total = self.db.scalar(select(func.count()).select_from(Requirement).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(Requirement).where(*criteria).offset((page - 1) * page_size).limit(page_size)
            ).all()
        )
        return items, total

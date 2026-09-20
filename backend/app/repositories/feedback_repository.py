from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Feedback
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    def __init__(self, db: Session):
        super().__init__(db, Feedback)

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Feedback | None:
        stmt = select(Feedback).where(Feedback.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(Feedback.submitter_id == user_id)
        return self.db.scalar(stmt)

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Feedback], int]:
        criteria = [] if data_scope is DataScope.ALL else [Feedback.submitter_id == user_id]
        total = self.db.scalar(select(func.count()).select_from(Feedback).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(Feedback).where(*criteria).offset((page - 1) * page_size).limit(page_size)
            ).all()
        )
        return items, total

from typing import Generic, TypeVar, Type
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model

    def get(self, entity_id: int) -> T | None:
        return self.db.get(self.model, entity_id)

    def list(self, page: int = 1, page_size: int = 20):
        total = self.db.scalar(select(func.count()).select_from(self.model)) or 0
        items = self.db.scalars(
            select(self.model).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return items, total

    def update_with_revision(self, entity_id: int, revision: int, values: dict) -> bool:
        result = self.db.execute(
            update(self.model)
            .where(self.model.id == entity_id, self.model.revision == revision)
            .values(**values, revision=self.model.revision + 1)
        )
        return bool(result.rowcount)

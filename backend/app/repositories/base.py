from typing import Any, TypeVar, cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository[T]:
    def __init__(self, db: Session, model: type[T]):
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
        model = cast(Any, self.model)
        id_column = model.id
        revision_column = model.revision
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(self.model)
                .where(id_column == entity_id, revision_column == revision)
                .values(**values, revision=revision_column + 1)
            ),
        )
        return bool(result.rowcount)

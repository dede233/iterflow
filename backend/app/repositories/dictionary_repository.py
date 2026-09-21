from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Dictionary, DictionaryItem
from app.repositories.base import BaseRepository


class DictionaryRepository(BaseRepository[Dictionary]):
    def __init__(self, db: Session):
        super().__init__(db, Dictionary)

    def get_by_code(self, code: str) -> Dictionary | None:
        return self.db.scalar(select(Dictionary).where(Dictionary.code == code))

    def list_enabled(self) -> list[Dictionary]:
        return list(
            self.db.scalars(
                select(Dictionary).where(Dictionary.enabled.is_(True)).order_by(Dictionary.code)
            ).all()
        )


class DictionaryItemRepository(BaseRepository[DictionaryItem]):
    def __init__(self, db: Session):
        super().__init__(db, DictionaryItem)

    def list_by_dictionary(
        self, dictionary_id: int, *, enabled_only: bool = False
    ) -> list[DictionaryItem]:
        stmt = select(DictionaryItem).where(DictionaryItem.dictionary_id == dictionary_id)
        if enabled_only:
            stmt = stmt.where(DictionaryItem.enabled.is_(True))
        return list(
            self.db.scalars(stmt.order_by(DictionaryItem.sort_order, DictionaryItem.id)).all()
        )

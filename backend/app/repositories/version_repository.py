from sqlalchemy.orm import Session
from app.models.entities import Version
from app.repositories.base import BaseRepository


class VersionRepository(BaseRepository[Version]):
    def __init__(self, db: Session):
        super().__init__(db, Version)

from sqlalchemy.orm import Session
from app.models.entities import Requirement
from app.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, db: Session):
        super().__init__(db, Requirement)

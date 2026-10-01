from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Requirement
from app.models.enums import DataScope, Priority, RequirementSource, RequirementStatus
from app.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, db: Session):
        super().__init__(db, Requirement)

    @staticmethod
    def self_criterion(user_id: int):
        return or_(Requirement.owner_id == user_id, Requirement.created_by == user_id)

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Requirement | None:
        stmt = select(Requirement).where(Requirement.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(self.self_criterion(user_id))
        return self.db.scalar(stmt)

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
        *,
        keyword: str | None = None,
        status: RequirementStatus | None = None,
        priority: Priority | None = None,
        source: RequirementSource | None = None,
        current_version_id: int | None = None,
        owner_id: int | None = None,
    ) -> tuple[list[Requirement], int]:
        criteria: list[ColumnElement[bool]] = []
        if data_scope is not DataScope.ALL:
            criteria.append(self.self_criterion(user_id))
        if keyword and keyword.strip():
            literal = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{literal}%"
            criteria.append(
                or_(
                    Requirement.requirement_no.ilike(pattern, escape="\\"),
                    Requirement.title.ilike(pattern, escape="\\"),
                )
            )
        for column, value in (
            (Requirement.status, status),
            (Requirement.priority, priority),
            (Requirement.source, source),
            (Requirement.current_version_id, current_version_id),
            (Requirement.owner_id, owner_id),
        ):
            if value is not None:
                criteria.append(column == value)
        total = self.db.scalar(select(func.count()).select_from(Requirement).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(Requirement)
                .where(*criteria)
                # Stable, deterministic ordering so pagination never reorders rows.
                .order_by(Requirement.created_at.desc(), Requirement.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

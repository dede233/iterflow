from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import DataScope
from app.repositories.base import BaseRepository


class VersionRepository(BaseRepository[Version]):
    def __init__(self, db: Session):
        super().__init__(db, Version)

    @staticmethod
    def self_criterion(user_id: int):
        return or_(Version.owner_id == user_id, Version.created_by == user_id)

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Version | None:
        stmt = select(Version).where(Version.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(self.self_criterion(user_id))
        return self.db.scalar(stmt)

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Version], int]:
        criteria = [] if data_scope is DataScope.ALL else [self.self_criterion(user_id)]
        total = self.db.scalar(select(func.count()).select_from(Version).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(Version)
                .where(*criteria)
                # Stable, deterministic ordering so pagination never reorders rows.
                .order_by(Version.created_at.desc(), Version.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    # ------------------------------------------------------------------ #
    # VersionRequirement relation queries (the relation model is the      #
    # source of truth; Requirement.current_version_id is a fast index).   #
    # ------------------------------------------------------------------ #
    def active_requirements(self, version_id: int) -> list[Requirement]:
        return list(
            self.db.scalars(
                select(Requirement)
                .join(VersionRequirement, VersionRequirement.requirement_id == Requirement.id)
                .where(
                    VersionRequirement.version_id == version_id,
                    VersionRequirement.active.is_(True),
                )
                .order_by(Requirement.id.asc())
            ).all()
        )

    def active_relation(self, version_id: int, requirement_id: int) -> VersionRequirement | None:
        return self.db.scalar(
            select(VersionRequirement).where(
                VersionRequirement.version_id == version_id,
                VersionRequirement.requirement_id == requirement_id,
                VersionRequirement.active.is_(True),
            )
        )

    def active_relation_of_requirement(self, requirement_id: int) -> VersionRequirement | None:
        return self.db.scalar(
            select(VersionRequirement).where(
                VersionRequirement.requirement_id == requirement_id,
                VersionRequirement.active.is_(True),
            )
        )

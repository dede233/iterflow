from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import DataScope, VersionStatus
from app.repositories.base import BaseRepository
from app.repositories.requirement_repository import RequirementRepository


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
        *,
        keyword: str | None = None,
        status: VersionStatus | None = None,
        planned_release_from: date | None = None,
        planned_release_to: date | None = None,
        owner_id: int | None = None,
    ) -> tuple[list[Version], int]:
        criteria: list[ColumnElement[bool]] = []
        if data_scope is not DataScope.ALL:
            criteria.append(self.self_criterion(user_id))
        if keyword and keyword.strip():
            literal = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{literal}%"
            criteria.append(
                or_(
                    Version.version_no.ilike(pattern, escape="\\"),
                    Version.name.ilike(pattern, escape="\\"),
                )
            )
        if status is not None:
            criteria.append(Version.status == status)
        if owner_id is not None:
            criteria.append(Version.owner_id == owner_id)
        if planned_release_from is not None:
            criteria.append(Version.planned_release_date >= planned_release_from)
        if planned_release_to is not None:
            criteria.append(Version.planned_release_date <= planned_release_to)
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

    def active_requirements_scoped(
        self, version_id: int, user_id: int, data_scope: DataScope
    ) -> list[Requirement]:
        statement = (
            select(Requirement)
            .join(VersionRequirement, VersionRequirement.requirement_id == Requirement.id)
            .where(
                VersionRequirement.version_id == version_id,
                VersionRequirement.active.is_(True),
            )
        )
        if data_scope is not DataScope.ALL:
            statement = statement.where(RequirementRepository.self_criterion(user_id))
        return list(self.db.scalars(statement.order_by(Requirement.id.asc())).all())

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

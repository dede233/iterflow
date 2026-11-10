from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.domain.version_progress import effective_version_status_expression
from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import DataScope, VersionStatus
from app.repositories.base import BaseRepository
from app.repositories.requirement_repository import RequirementRepository


class VersionRepository(BaseRepository[Version]):
    def __init__(self, db: Session):
        super().__init__(db, Version)

    @staticmethod
    def with_progress(item: Version, status: str) -> Version:
        # A separate, unmapped attribute cannot dirty the persisted status.
        item.__dict__["_effective_status"] = VersionStatus(status)
        return item

    def get(self, entity_id: int) -> Version | None:
        row = self.db.execute(
            select(Version, effective_version_status_expression())
            .where(Version.id == entity_id)
            .execution_options(populate_existing=True)
        ).first()
        return self.with_progress(*row) if row is not None else None

    @staticmethod
    def self_criterion(user_id: int):
        return or_(Version.owner_id == user_id, Version.created_by == user_id)

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Version | None:
        stmt = select(Version, effective_version_status_expression()).where(Version.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(self.self_criterion(user_id))
        row = self.db.execute(stmt.execution_options(populate_existing=True)).first()
        return self.with_progress(*row) if row is not None else None

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
        *,
        system_id: int | None = None,
        keyword: str | None = None,
        status: VersionStatus | None = None,
        planned_release_from: date | None = None,
        planned_release_to: date | None = None,
        owner_id: int | None = None,
    ) -> tuple[list[Version], int]:
        criteria: list[ColumnElement[bool]] = []
        if data_scope is not DataScope.ALL:
            criteria.append(self.self_criterion(user_id))
        if system_id is not None:
            criteria.append(Version.system_id == system_id)
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
            criteria.append(effective_version_status_expression() == status)
        if owner_id is not None:
            criteria.append(Version.owner_id == owner_id)
        if planned_release_from is not None:
            criteria.append(Version.planned_release_date >= planned_release_from)
        if planned_release_to is not None:
            criteria.append(Version.planned_release_date <= planned_release_to)
        total = self.db.scalar(select(func.count()).select_from(Version).where(*criteria)) or 0
        rows = self.db.execute(
            select(Version, effective_version_status_expression())
            .where(*criteria)
            # Stable, deterministic ordering so pagination never reorders rows.
            .order_by(Version.created_at.desc(), Version.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        ).all()
        items = [self.with_progress(*row) for row in rows]
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
                    Requirement.deleted_at.is_(None),
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
                Requirement.deleted_at.is_(None),
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

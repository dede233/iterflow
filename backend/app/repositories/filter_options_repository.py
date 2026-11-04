from typing import Any

from sqlalchemy import ColumnElement, Select, String, case, cast, false, func, literal, select, true
from sqlalchemy.orm import Session

from app.models.entities import Requirement, RequirementParticipant, User, Version
from app.models.enums import DataScope, UserStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.version_repository import VersionRepository


class FilterOptionsRepository:
    """Small labels from visible business relationships, never a user directory."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _requirement_scope(user_id: int, scope: DataScope) -> list[ColumnElement[bool]]:
        criteria: list[ColumnElement[bool]] = [Requirement.deleted_at.is_(None)]
        if scope is not DataScope.ALL:
            criteria.append(RequirementRepository.self_criterion(user_id))
        return criteria

    @staticmethod
    def _person_label():
        return User.display_name.concat(
            case((User.status == UserStatus.ACTIVE, ""), else_="(已停用)")
        )

    def participants(self, user_id: int, scope: DataScope):
        visible = select(Requirement.id).where(*self._requirement_scope(user_id, scope))
        people = select(RequirementParticipant.user_id).where(
            RequirementParticipant.active.is_(True),
            RequirementParticipant.requirement_id.in_(visible),
        )
        return select(User.id, self._person_label().label("label")).where(User.id.in_(people))

    def owners(self, user_id: int, scope: DataScope):
        versions = select(Version.owner_id)
        if scope is not DataScope.ALL:
            versions = versions.where(VersionRepository.self_criterion(user_id))
        return select(User.id, self._person_label().label("label")).where(User.id.in_(versions))

    def requirement_versions(self, user_id: int, scope: DataScope, can_view_versions: bool):
        visible_versions = select(Requirement.current_version_id).where(
            *self._requirement_scope(user_id, scope),
            Requirement.current_version_id.is_not(None),
        )
        readable = (
            (true() if scope is DataScope.ALL else VersionRepository.self_criterion(user_id))
            if can_view_versions
            else false()
        )
        # Search the same safe label we return, so hidden names cannot become an oracle.
        label = case(
            (readable, cast(Version.version_no, String).concat(" · ").concat(Version.name)),
            else_=literal("版本 #").concat(cast(Version.id, String)).concat("(无查看权限)"),
        )
        return select(Version.id, label.label("label")).where(Version.id.in_(visible_versions))

    def page(
        self,
        query: Select,
        keyword: str,
        page: int,
        page_size: int,
        selected_id: int | None,
    ) -> tuple[list[dict[str, Any]], int]:
        options = query.subquery()
        criteria = []
        if selected_id is not None:
            criteria.append(options.c.id == selected_id)
        if keyword.strip():
            literal_keyword = (
                keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            criteria.append(options.c.label.ilike(f"%{literal_keyword}%", escape="\\"))
        total = self.db.scalar(select(func.count()).select_from(options).where(*criteria)) or 0
        rows = self.db.execute(
            select(options.c.id, options.c.label)
            .where(*criteria)
            .order_by(options.c.label, options.c.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings()
        return [dict(row) for row in rows], total

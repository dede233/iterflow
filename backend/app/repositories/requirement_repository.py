from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Requirement, RequirementParticipant, User
from app.models.enums import DataScope, Priority, RequirementSource, RequirementStatus
from app.repositories.base import BaseRepository


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, db: Session):
        super().__init__(db, Requirement)

    def get(self, entity_id: int) -> Requirement | None:
        return self.db.scalar(
            select(Requirement).where(Requirement.id == entity_id, Requirement.deleted_at.is_(None))
        )

    @staticmethod
    def self_criterion(user_id: int):
        participant = select(RequirementParticipant.requirement_id).where(
            RequirementParticipant.user_id == user_id,
            RequirementParticipant.active.is_(True),
        )
        return or_(
            Requirement.owner_id == user_id,
            Requirement.created_by == user_id,
            Requirement.id.in_(participant),
        )

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Requirement | None:
        stmt = select(Requirement).where(
            Requirement.id == entity_id, Requirement.deleted_at.is_(None)
        )
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(self.self_criterion(user_id))
        item = self.db.scalar(stmt)
        if item:
            self.populate_handlers([item])
        return item

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
        participant_id: int | None = None,
        participant_role: str | None = None,
    ) -> tuple[list[Requirement], int]:
        criteria: list[ColumnElement[bool]] = [Requirement.deleted_at.is_(None)]
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
        if participant_id is not None or participant_role is not None:
            members = select(RequirementParticipant.requirement_id).where(
                RequirementParticipant.active.is_(True)
            )
            if participant_id is not None:
                members = members.where(RequirementParticipant.user_id == participant_id)
            if participant_role is not None:
                members = members.where(RequirementParticipant.role == participant_role)
            criteria.append(Requirement.id.in_(members))
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
        self.populate_handlers(items)
        return items, total

    def populate_handlers(self, items: list[Requirement]) -> None:
        grouped: dict[int, list] = {}
        if not items:
            return
        for person, user in self.db.execute(
            select(RequirementParticipant, User)
            .join(User)
            .where(
                RequirementParticipant.requirement_id.in_([r.id for r in items]),
                RequirementParticipant.active.is_(True),
            )
        ):
            grouped.setdefault(person.requirement_id, []).append((person, user))
        for item in items:
            stage = item.paused_from if item.status == "PAUSED" else item.status
            role = {
                "DRAFT": "CONFIRM",
                "CONFIRMED": "DEVELOP",
                "DEVELOPING": "DEVELOP",
                "TESTING": "ACCEPT",
            }.get(stage or "")
            if (
                item.status not in {"ONLINE", "CANCELED"}
                and not item.legacy_completed
                and item.confirmed_revision != item.content_revision
            ):
                role = "CONFIRM"
            roles = {role}
            if stage in {"CONFIRMED", "DEVELOPING"} and item.design_status in {
                "PENDING",
                "IN_PROGRESS",
            }:
                roles.add("DESIGN")
            names = {
                u.id: {
                    "id": u.id,
                    "display_name": u.display_name + ("(已停用)" if u.status != "ACTIVE" else ""),
                }
                for p, u in grouped.get(item.id, [])
                if p.role in roles
            }
            item.__dict__["_current_handlers"] = list(names.values())

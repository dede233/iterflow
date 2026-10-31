from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import BusinessModule, BusinessSystem, Feedback, User
from app.models.enums import DataScope, FeedbackStatus, FeedbackType, FeedbackUrgency
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    def __init__(self, db: Session):
        super().__init__(db, Feedback)

    def display_names(
        self, feedback_ids: list[int]
    ) -> dict[int, tuple[str | None, str | None, str | None]]:
        """Read only labels belonging to the feedbacks already authorized by the caller."""
        if not feedback_ids:
            return {}
        rows = self.db.execute(
            select(Feedback.id, User.display_name, BusinessSystem.name, BusinessModule.name)
            .select_from(Feedback)
            .outerjoin(User, User.id == Feedback.submitter_id)
            .outerjoin(BusinessSystem, BusinessSystem.id == Feedback.system_id)
            .outerjoin(BusinessModule, BusinessModule.id == Feedback.module_id)
            .where(Feedback.id.in_(feedback_ids))
        ).all()
        return {row[0]: (row[1], row[2], row[3]) for row in rows}

    def get_scoped(self, entity_id: int, user_id: int, data_scope: DataScope) -> Feedback | None:
        stmt = select(Feedback).where(Feedback.id == entity_id)
        if data_scope is not DataScope.ALL:
            stmt = stmt.where(Feedback.submitter_id == user_id)
        return self.db.scalar(stmt)

    @staticmethod
    def _filters(
        user_id: int,
        data_scope: DataScope,
        *,
        status: FeedbackStatus | None,
        feedback_type: FeedbackType | None,
        urgency: FeedbackUrgency | None,
        system_id: int | None,
        module_id: int | None,
        keyword: str | None,
    ) -> list[ColumnElement[bool]]:
        # The data-scope predicate is always combined (AND) with the caller's
        # filters so a filter can never widen access beyond the caller's scope.
        criteria: list[ColumnElement[bool]] = []
        if data_scope is not DataScope.ALL:
            criteria.append(Feedback.submitter_id == user_id)
        if status is not None:
            criteria.append(Feedback.status == status)
        if feedback_type is not None:
            criteria.append(Feedback.feedback_type == feedback_type)
        if urgency is not None:
            criteria.append(Feedback.urgency == urgency)
        if system_id is not None:
            criteria.append(Feedback.system_id == system_id)
        if module_id is not None:
            criteria.append(Feedback.module_id == module_id)
        if keyword:
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{escaped}%"
            criteria.append(
                or_(
                    Feedback.feedback_no.ilike(like, escape="\\"),
                    Feedback.title.ilike(like, escape="\\"),
                    Feedback.description.ilike(like, escape="\\"),
                )
            )
        return criteria

    def list_scoped(
        self,
        user_id: int,
        data_scope: DataScope,
        page: int = 1,
        page_size: int = 20,
        *,
        status: FeedbackStatus | None = None,
        feedback_type: FeedbackType | None = None,
        urgency: FeedbackUrgency | None = None,
        system_id: int | None = None,
        module_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[list[Feedback], int]:
        criteria = self._filters(
            user_id,
            data_scope,
            status=status,
            feedback_type=feedback_type,
            urgency=urgency,
            system_id=system_id,
            module_id=module_id,
            keyword=keyword,
        )
        total = self.db.scalar(select(func.count()).select_from(Feedback).where(*criteria)) or 0
        items = list(
            self.db.scalars(
                select(Feedback)
                .where(*criteria)
                # Stable, deterministic ordering so pagination never reorders rows.
                .order_by(Feedback.created_at.desc(), Feedback.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

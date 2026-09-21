from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Feedback
from app.models.enums import DataScope, FeedbackStatus, FeedbackType, FeedbackUrgency
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    def __init__(self, db: Session):
        super().__init__(db, Feedback)

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
            like = f"%{keyword}%"
            criteria.append(
                or_(
                    Feedback.feedback_no.ilike(like),
                    Feedback.title.ilike(like),
                    Feedback.description.ilike(like),
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

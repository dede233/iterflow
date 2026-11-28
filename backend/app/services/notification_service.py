from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.models.entities import AdProduction, Notification
from app.services.ad_production_notifications import AD_PRODUCTION_NOTIFICATION_ENTITIES


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _visible() -> ColumnElement[bool]:
        return (
            ~select(AdProduction.id)
            .where(
                AdProduction.id == Notification.entity_id,
                AdProduction.deleted_at.is_not(None),
                Notification.entity_type.in_(AD_PRODUCTION_NOTIFICATION_ENTITIES),
            )
            .exists()
        )

    def list_for_user(self, user_id: int, *, unread_only: bool = False) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id, self._visible())
            .order_by(Notification.created_at.desc())
        )
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list(self.db.scalars(statement.limit(100)).all())

    def unread_count(self, user_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user_id, Notification.read_at.is_(None), self._visible()
                )
            )
            or 0
        )

    def read_all(self, user_id: int) -> int:
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None), self._visible())
            .values(read_at=datetime.now(UTC))
        )
        self.db.commit()
        return int(cast(CursorResult[Any], result).rowcount or 0)

    def mark_read(self, notification_id: int, user_id: int) -> dict[str, bool]:
        item = self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
                self._visible(),
            )
        )
        if item is not None:
            item.read_at = datetime.now(UTC)
            self.db.commit()
        return {"ok": True}

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Notification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: int, *, unread_only: bool = False) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list(self.db.scalars(statement.limit(100)).all())

    def mark_read(self, notification_id: int, user_id: int) -> dict[str, bool]:
        item = self.db.get(Notification, notification_id)
        if item is not None and item.user_id == user_id and item.read_at is None:
            item.read_at = datetime.now(UTC)
            self.db.commit()
        return {"ok": True}

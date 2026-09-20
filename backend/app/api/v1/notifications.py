from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return db.scalars(stmt.limit(100)).all()


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    item = db.get(Notification, notification_id)
    if item and item.user_id == user.id and item.read_at is None:
        item.read_at = datetime.now(UTC)
        db.commit()
    return {"ok": True}

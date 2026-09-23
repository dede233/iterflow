from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import User
from app.schemas.notification import NotificationOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return NotificationService(db).list_for_user(user.id, unread_only=unread_only)


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return NotificationService(db).mark_read(notification_id, user.id)

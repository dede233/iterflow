from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.notification import (
    NotificationOut,
    NotificationReadAllResult,
    NotificationUnreadCount,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return NotificationService(db).list_for_user(user.id, unread_only=unread_only)


@router.get(
    "/unread-count",
    response_model=NotificationUnreadCount,
    responses=api_error_responses(401),
    summary="当前用户真实未读总数",
    description="仅当前登录用户自己的通知; 不依赖业务权限或 DataScope。",
)
def unread_count(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"unread_count": NotificationService(db).unread_count(user.id)}


@router.post(
    "/read-all",
    response_model=NotificationReadAllResult,
    responses=api_error_responses(401),
    summary="当前用户全部通知已读",
    description="仅当前登录用户自己的通知; 不依赖业务权限或 DataScope。",
)
def read_all(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {"updated_count": NotificationService(db).read_all(user.id)}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return NotificationService(db).mark_read(notification_id, user.id)

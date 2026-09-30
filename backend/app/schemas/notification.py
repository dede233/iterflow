from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: NotificationType
    title: str
    content: str
    entity_type: str | None
    entity_id: int | None
    read_at: datetime | None
    created_at: datetime


class NotificationUnreadCount(BaseModel):
    unread_count: int = Field(ge=0)


class NotificationReadAllResult(BaseModel):
    updated_count: int = Field(ge=0)

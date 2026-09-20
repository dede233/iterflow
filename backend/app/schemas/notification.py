from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    entity_type: str | None
    entity_id: int | None
    read_at: datetime | None
    created_at: datetime

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditOperatorOut(BaseModel):
    """A minimal, non-sensitive representation of the audit operator."""

    id: int
    username: str
    display_name: str


class AuditOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int | None
    action: str
    operator: AuditOperatorOut | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditOut]
    page: int
    size: int
    total: int

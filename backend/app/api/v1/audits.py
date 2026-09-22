from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.schemas.audit import AuditOut, AuditPage
from app.services.audit_query_service import AuditQueryService

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("", response_model=AuditPage)
def list_audits(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    entity_type: str | None = Query(None, min_length=1, max_length=32),
    entity_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, min_length=1, max_length=64),
    operator_id: int | None = Query(None, ge=1),
    time_from: datetime | None = Query(None),
    time_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.audit.view")),
):
    items, total = AuditQueryService(db).list(
        user,
        page=page,
        size=size,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        operator_id=operator_id,
        time_from=time_from,
        time_to=time_to,
    )
    return {"items": items, "page": page, "size": size, "total": total}


@router.get("/{audit_id}", response_model=AuditOut)
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.audit.view")),
):
    return AuditQueryService(db).get(audit_id, user)

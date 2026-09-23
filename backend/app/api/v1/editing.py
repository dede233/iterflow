from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import User
from app.models.enums import EditingEntityType
from app.services.editing_service import EditingService

router = APIRouter(prefix="/editing", tags=["editing"])


class EditHeartbeat(BaseModel):
    entity_type: EditingEntityType
    entity_id: int


@router.post("/start")
def start_edit(
    payload: EditHeartbeat,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    EditingService.authorize_entity(db, payload.entity_type, payload.entity_id, user.id)
    existing = EditingService().start(
        payload.entity_type, payload.entity_id, user.id, user.display_name
    )
    return {"existing_editor": existing}


@router.post("/heartbeat")
def heartbeat(
    payload: EditHeartbeat,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    EditingService.authorize_entity(db, payload.entity_type, payload.entity_id, user.id)
    existing = EditingService().heartbeat(
        payload.entity_type,
        payload.entity_id,
        user.id,
        user.display_name,
    )
    return {"ok": existing is None, "existing_editor": existing}


@router.post("/end")
def end_edit(
    payload: EditHeartbeat,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    EditingService.authorize_entity(db, payload.entity_type, payload.entity_id, user.id)
    EditingService().end(payload.entity_type, payload.entity_id, user.id)
    return {"ok": True}

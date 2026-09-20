from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user
from app.models.entities import User
from app.models.enums import EditingEntityType
from app.services.editing_service import EditingService

router = APIRouter(prefix="/editing", tags=["editing"])


class EditHeartbeat(BaseModel):
    entity_type: EditingEntityType
    entity_id: int


@router.post("/start")
def start_edit(payload: EditHeartbeat, user: User = Depends(current_user)):
    existing = EditingService().start(
        payload.entity_type, payload.entity_id, user.id, user.display_name
    )
    return {"existing_editor": existing}


@router.post("/heartbeat")
def heartbeat(payload: EditHeartbeat, user: User = Depends(current_user)):
    existing = EditingService().heartbeat(
        payload.entity_type,
        payload.entity_id,
        user.id,
        user.display_name,
    )
    return {"ok": existing is None, "existing_editor": existing}


@router.post("/end")
def end_edit(payload: EditHeartbeat, user: User = Depends(current_user)):
    EditingService().end(payload.entity_type, payload.entity_id, user.id)
    return {"ok": True}

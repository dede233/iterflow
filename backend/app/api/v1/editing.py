from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.deps import current_user
from app.models.entities import User
from app.services.editing_service import EditingService

router = APIRouter(prefix="/editing", tags=["editing"])


class EditHeartbeat(BaseModel):
    entity_type: str = Field(max_length=32)
    entity_id: int


@router.post("/start")
def start_edit(payload: EditHeartbeat, user: User = Depends(current_user)):
    existing = EditingService().start(payload.entity_type, payload.entity_id, user.id, user.display_name)
    return {"existing_editor": existing}


@router.post("/heartbeat")
def heartbeat(payload: EditHeartbeat, user: User = Depends(current_user)):
    EditingService().heartbeat(payload.entity_type, payload.entity_id, user.id, user.display_name)
    return {"ok": True}


@router.post("/end")
def end_edit(payload: EditHeartbeat, user: User = Depends(current_user)):
    EditingService().end(payload.entity_type, payload.entity_id, user.id)
    return {"ok": True}

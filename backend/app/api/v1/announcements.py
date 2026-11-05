from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementNotice,
    AnnouncementOut,
    AnnouncementPage,
    AnnouncementUpdate,
)
from app.schemas.common import RevisionPayload
from app.services.announcement_service import IMAGE_ENTITY, AnnouncementService
from app.services.file_service import FileService

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"],
    responses=api_error_responses(401, 403, 404, 409, 422),
)


@router.get("", response_model=AnnouncementPage)
def list_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manage: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return AnnouncementService(db).listing(user, page, page_size, manage)


@router.get("/notice", response_model=AnnouncementNotice)
def announcement_notice(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return AnnouncementService(db).notice(user)


@router.post("", response_model=AnnouncementOut)
def create_announcement(
    payload: AnnouncementCreate, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return AnnouncementService(db).create(payload, user)


@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(
    announcement_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    service = AnnouncementService(db)
    return service.out(service.get(announcement_id, user), user)


@router.patch("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return AnnouncementService(db).update(announcement_id, payload, user)


@router.post("/{announcement_id}/publish", response_model=AnnouncementOut)
def publish_announcement(
    announcement_id: int,
    payload: RevisionPayload,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return AnnouncementService(db).publish(announcement_id, payload.revision, user)


@router.post("/{announcement_id}/read", response_model=AnnouncementOut)
def read_announcement(
    announcement_id: int,
    payload: RevisionPayload,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return AnnouncementService(db).mark_read(announcement_id, payload.revision, user)


@router.get(
    "/{announcement_id}/images/{file_id}",
    response_class=StreamingResponse,
    responses={
        200: {"content": {media: {} for media in ("image/png", "image/jpeg", "image/webp")}}
    },
)
def announcement_image(
    announcement_id: int,
    file_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    AnnouncementService(db).get(announcement_id, user)
    item, stream = FileService(db).open_authorized_attachment(
        file_id, entity_type=IMAGE_ENTITY, entity_id=announcement_id
    )
    background.add_task(stream.close)
    return StreamingResponse(
        stream,
        media_type=item.mime_type,
        background=background,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )

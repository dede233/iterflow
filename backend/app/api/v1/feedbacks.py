from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError, PermissionDenied
from app.models.entities import Feedback, User
from app.models.enums import FeedbackStatus, FeedbackType, FeedbackUrgency
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.user_repository import UserRepository
from app.schemas.comment import CommentCreate, CommentOut
from app.schemas.feedback import (
    FeedbackConvertRequest,
    FeedbackCreate,
    FeedbackOut,
    FeedbackPage,
    FeedbackStatusChange,
    FeedbackUpdate,
)
from app.schemas.file import AttachmentOut
from app.schemas.requirement import RequirementOut
from app.services.comment_service import CommentService
from app.services.feedback_service import FeedbackService
from app.services.file_service import MAX_UPLOAD_SIZE, FileService, validate_upload

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


def _scoped_feedback_or_404(db: Session, user: User, feedback_id: int) -> Feedback:
    scope = UserRepository(db).data_scope(user.id)
    item = FeedbackRepository(db).get_scoped(feedback_id, user.id, scope)
    if item is None:
        raise NotFoundError("反馈不存在")
    return item


def _content_disposition(original_name: str) -> str:
    cleaned = original_name.replace("\r", "").replace("\n", "").replace("\x00", "") or "file"
    return f"attachment; filename*=UTF-8''{quote(cleaned, safe='')}"


@router.get("", response_model=FeedbackPage)
def list_feedbacks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: FeedbackStatus | None = Query(None),
    feedback_type: FeedbackType | None = Query(None),
    urgency: FeedbackUrgency | None = Query(None),
    system_id: int | None = Query(None),
    module_id: int | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    # Filter ids must exist (422 otherwise); disabled system/module are allowed
    # here so historical feedback stays filterable.
    FeedbackService(db).validate_filter_system_module(system_id, module_id)
    scope = UserRepository(db).data_scope(user.id)
    normalized_keyword = keyword.strip() if keyword and keyword.strip() else None
    items, total = FeedbackRepository(db).list_scoped(
        user.id,
        scope,
        page,
        page_size,
        status=status,
        feedback_type=feedback_type,
        urgency=urgency,
        system_id=system_id,
        module_id=module_id,
        keyword=normalized_keyword,
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("", response_model=FeedbackOut)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.create")),
):
    return FeedbackService(db).create(payload, user.id)


@router.get("/{feedback_id}", response_model=FeedbackOut)
def get_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    return _scoped_feedback_or_404(db, user, feedback_id)


@router.patch("/{feedback_id}", response_model=FeedbackOut)
def update_feedback(
    feedback_id: int,
    payload: FeedbackUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.edit")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    return FeedbackService(db).update(feedback_id, payload, user.id)


@router.patch("/{feedback_id}/status", response_model=FeedbackOut)
def change_feedback_status(
    feedback_id: int,
    payload: FeedbackStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.edit")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    scope = UserRepository(db).data_scope(user.id)
    return FeedbackService(db).change_status(
        feedback_id, payload, user.id, viewer_scope=scope, viewer_id=user.id
    )


# --------------------------------------------------------------------------- #
# Attachments — business relation stores only file_id; access is authorized by
# the feedback data scope + the FEEDBACK attachment relation (not file owner).
# --------------------------------------------------------------------------- #
@router.get("/{feedback_id}/attachments", response_model=list[AttachmentOut])
def list_feedback_attachments(
    feedback_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    files = FeedbackService(db).list_attachment_files(feedback_id)
    return [
        AttachmentOut(
            file_id=f.id,
            original_name=f.original_name,
            size=f.size,
            mime_type=f.mime_type,
            created_at=f.created_at,
            created_by=f.created_by,
        )
        for f in files
    ]


@router.post("/{feedback_id}/attachments", response_model=AttachmentOut)
async def add_feedback_attachment(
    feedback_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # Attaching is part of authoring feedback; gated by create + data scope so a
    # SELF submitter can attach to their own, and ALL operators to any in scope.
    user: User = Depends(require_permission("rd.feedback.create")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    original_name = validate_upload(
        size=len(content),
        mime_type=file.content_type,
        original_name=file.filename,
        content=content,
    )
    service = FeedbackService(db)
    stored = FileService(db).upload(
        content=content,
        original_name=original_name,
        mime_type=file.content_type or "application/octet-stream",
        actor=user,
    )
    service.attach_file(feedback_id, stored.id, user.id)
    return AttachmentOut(
        file_id=stored.id,
        original_name=stored.original_name,
        size=stored.size,
        mime_type=stored.mime_type,
        created_at=stored.created_at,
        created_by=stored.created_by,
    )


@router.get("/{feedback_id}/attachments/{file_id}/download")
def download_feedback_attachment(
    feedback_id: int,
    file_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
) -> Response:
    _scoped_feedback_or_404(db, user, feedback_id)
    file_service = FileService(db)
    item, stream = file_service.open_authorized_attachment(
        file_id, entity_type="FEEDBACK", entity_id=feedback_id
    )
    background_tasks.add_task(stream.close)
    return StreamingResponse(
        stream,
        media_type=item.mime_type,
        headers={"Content-Disposition": _content_disposition(item.original_name)},
        background=background_tasks,
    )


# --------------------------------------------------------------------------- #
# Comments (FEEDBACK entity only in Phase 3)                                  #
# --------------------------------------------------------------------------- #
@router.get("/{feedback_id}/comments", response_model=list[CommentOut])
def list_feedback_comments(
    feedback_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    return CommentService(db).list_for_entity("FEEDBACK", feedback_id)


@router.post("/{feedback_id}/comments", response_model=CommentOut)
def create_feedback_comment(
    feedback_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    return CommentService(db).create_for_entity("FEEDBACK", feedback_id, payload.content, user.id)


@router.post("/{feedback_id}/convert", response_model=RequirementOut)
def convert_feedback(
    feedback_id: int,
    payload: FeedbackConvertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.convert")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    if payload.type.value == "LINK_EXISTING":
        permissions = UserRepository(db).permission_codes(user.id)
        if "*" not in permissions and "rd.requirement.view" not in permissions:
            raise PermissionDenied()
    scope = UserRepository(db).data_scope(user.id)
    return FeedbackService(db).convert(
        feedback_id, payload, user.id, viewer_scope=scope, viewer_id=user.id
    )

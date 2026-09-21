from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import Feedback, User
from app.models.enums import FeedbackStatus, FeedbackType, FeedbackUrgency
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.feedback import (
    FeedbackConvertRequest,
    FeedbackCreate,
    FeedbackOut,
    FeedbackPage,
    FeedbackStatusChange,
    FeedbackUpdate,
)
from app.schemas.requirement import RequirementOut
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


def _scoped_feedback_or_404(db: Session, user: User, feedback_id: int) -> Feedback:
    scope = UserRepository(db).data_scope(user.id)
    item = FeedbackRepository(db).get_scoped(feedback_id, user.id, scope)
    if item is None:
        raise NotFoundError("反馈不存在")
    return item


def _ensure_scoped_version(db: Session, user: User, version_id: int | None) -> None:
    if version_id is None:
        return
    scope = UserRepository(db).data_scope(user.id)
    if VersionRepository(db).get_scoped(version_id, user.id, scope) is None:
        raise NotFoundError("版本不存在")


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


@router.post("/{feedback_id}/convert", response_model=RequirementOut)
def convert_feedback(
    feedback_id: int,
    payload: FeedbackConvertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.convert")),
):
    _scoped_feedback_or_404(db, user, feedback_id)
    _ensure_scoped_version(db, user, payload.version_id)
    return FeedbackService(db).convert(feedback_id, payload, user.id)

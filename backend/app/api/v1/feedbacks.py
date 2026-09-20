from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import require_permission, current_user
from app.core.database import get_db
from app.models.entities import User
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackConvertRequest
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


@router.get("")
def list_feedbacks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_permission("rd.feedback.view"))):
    items, total = FeedbackRepository(db).list(page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("")
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.feedback.create"))):
    return FeedbackService(db).create(payload, user.id)


@router.get("/{feedback_id}")
def get_feedback(feedback_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.feedback.view"))):
    return FeedbackRepository(db).get(feedback_id)


@router.patch("/{feedback_id}")
def update_feedback(feedback_id: int, payload: FeedbackUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.feedback.edit"))):
    return FeedbackService(db).update(feedback_id, payload, user.id)


@router.post("/{feedback_id}/convert")
def convert_feedback(feedback_id: int, payload: FeedbackConvertRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.feedback.convert"))):
    return FeedbackService(db).convert(feedback_id, payload, user.id)

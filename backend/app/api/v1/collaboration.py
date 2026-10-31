from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_all_permissions, require_any_permission, require_permission
from app.api.v1.feedbacks import _scoped_feedback_or_404
from app.api.v1.requirements import _scoped_requirement_or_404
from app.core.database import get_db
from app.models.entities import User
from app.schemas.collaboration import (
    FeedbackCollaborationOut,
    FeedbackTransfer,
    ParticipantsChange,
    ParticipantsOut,
    PersonPage,
    RecipientsChange,
)
from app.services.collaboration_service import CollaborationService

router = APIRouter(tags=["collaboration"])


@router.get("/collaboration/people", response_model=PersonPage)
def people(
    kind: Literal["feedback", "requirement"],
    feedback_id: int | None = None,
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_any_permission(
            "rd.feedback.create", "rd.feedback.edit", "rd.requirement.create", "rd.requirement.edit"
        )
    ),
):
    submitter_id = user.id
    if kind == "feedback":
        if feedback_id is not None:
            ensure_all_permissions(user, db, "rd.feedback.edit")
            submitter_id = _scoped_feedback_or_404(db, user, feedback_id).submitter_id
        else:
            ensure_all_permissions(user, db, "rd.feedback.create")
    else:
        # The candidate directory is purpose-limited, not a user administration endpoint.
        from app.core.exceptions import PermissionDenied
        from app.repositories.user_repository import UserRepository

        codes = UserRepository(db).permission_codes(user.id)
        if not codes.intersection({"*", "rd.requirement.create", "rd.requirement.edit"}):
            raise PermissionDenied()
    return CollaborationService(db).people(kind, submitter_id, keyword, page, page_size)


@router.get("/feedbacks/{feedback_id}/collaboration", response_model=FeedbackCollaborationOut)
def feedback_collaboration(
    feedback_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.view")),
):
    return CollaborationService(db).feedback_view(_scoped_feedback_or_404(db, user, feedback_id))


@router.put("/feedbacks/{feedback_id}/recipients", response_model=FeedbackCollaborationOut)
def recipients(
    feedback_id: int,
    payload: RecipientsChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.edit")),
):
    return CollaborationService(db).change_recipients(
        _scoped_feedback_or_404(db, user, feedback_id),
        payload.recipient_ids,
        payload.revision,
        user.id,
    )


@router.post("/feedbacks/{feedback_id}/transfer", response_model=FeedbackCollaborationOut)
def transfer(
    feedback_id: int,
    payload: FeedbackTransfer,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.feedback.edit")),
):
    return CollaborationService(db).transfer(
        _scoped_feedback_or_404(db, user, feedback_id),
        payload.handler_id,
        payload.revision,
        payload.reason,
        user.id,
    )


@router.get("/requirements/{requirement_id}/participants", response_model=ParticipantsOut)
def participants(
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    return CollaborationService(db).participants_view(
        _scoped_requirement_or_404(db, user, requirement_id)
    )


@router.put("/requirements/{requirement_id}/participants", response_model=ParticipantsOut)
def change_participants(
    requirement_id: int,
    payload: ParticipantsChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    return CollaborationService(db).change_participants(
        _scoped_requirement_or_404(db, user, requirement_id), payload, user.id
    )

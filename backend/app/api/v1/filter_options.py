from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.schemas.filter_options import FilterOptionPage
from app.services.filter_options_service import FilterOptionsService

router = APIRouter(tags=["filter-options"])


@router.get("/requirements/filter-options/participants", response_model=FilterOptionPage)
def requirement_participant_options(
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    selected_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    return FilterOptionsService(db).list(
        "participants", user.id, keyword, page, page_size, selected_id
    )


@router.get("/requirements/filter-options/versions", response_model=FilterOptionPage)
def requirement_version_options(
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    selected_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    return FilterOptionsService(db).list(
        "requirement_versions", user.id, keyword, page, page_size, selected_id
    )


@router.get("/versions/filter-options/owners", response_model=FilterOptionPage)
def version_owner_options(
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    selected_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    return FilterOptionsService(db).list("owners", user.id, keyword, page, page_size, selected_id)

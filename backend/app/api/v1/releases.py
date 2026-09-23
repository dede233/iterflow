from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.release import ReleaseOut, ReleasePage
from app.services.release_query_service import ReleaseQueryService

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("", response_model=ReleasePage)
def list_releases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    version_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    return ReleaseQueryService(db).list_for_user(
        current,
        page=page,
        page_size=page_size,
        version_id=version_id,
    )


@router.get("/{release_id}", response_model=ReleaseOut, responses=api_error_responses(404))
def get_release(
    release_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    return ReleaseQueryService(db).get_for_user(release_id, current)

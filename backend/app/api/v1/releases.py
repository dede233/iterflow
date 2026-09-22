from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import Release, User, Version
from app.models.enums import DataScope
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.release import ReleasePage

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("", response_model=ReleasePage)
def list_releases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    # Release history is read-only and scoped through its owning Version.
    scope = UserRepository(db).data_scope(current.id)
    criteria = [] if scope is DataScope.ALL else [VersionRepository.self_criterion(current.id)]
    base = select(Release).join(Version, Version.id == Release.version_id).where(*criteria)
    total = (
        db.scalar(
            select(func.count())
            .select_from(Release)
            .join(Version, Version.id == Release.version_id)
            .where(*criteria)
        )
        or 0
    )
    items = list(
        db.scalars(
            base.order_by(Release.released_at.desc(), Release.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}

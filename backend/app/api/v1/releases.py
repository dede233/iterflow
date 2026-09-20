from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import Release, User, Version
from app.models.enums import DataScope
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get("")
def list_releases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    scope = UserRepository(db).data_scope(current.id)
    stmt = select(Release).join(Version, Version.id == Release.version_id)
    if scope is not DataScope.ALL:
        stmt = stmt.where(VersionRepository.self_criterion(current.id))
    items = db.scalars(
        stmt.order_by(Release.released_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size}

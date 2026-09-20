from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import User
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.version import (
    PublishVersionRequest,
    VersionCreate,
    VersionStatusChange,
    VersionUpdate,
)
from app.services.version_service import VersionService

router = APIRouter(prefix="/versions", tags=["versions"])


def _scoped_version_or_404(db: Session, user: User, version_id: int):
    scope = UserRepository(db).data_scope(user.id)
    item = VersionRepository(db).get_scoped(version_id, user.id, scope)
    if item is None:
        raise NotFoundError("版本不存在")
    return item


@router.get("")
def list_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    scope = UserRepository(db).data_scope(user.id)
    items, total = VersionRepository(db).list_scoped(user.id, scope, page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("")
def create_version(
    payload: VersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.create")),
):
    return VersionService(db).create(payload, user.id)


@router.get("/{version_id}")
def get_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    return _scoped_version_or_404(db, user, version_id)


@router.patch("/{version_id}")
def update_version(
    version_id: int,
    payload: VersionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.edit")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).update(version_id, payload, user.id)


@router.patch("/{version_id}/status")
def change_version_status(
    version_id: int,
    payload: VersionStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.status")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).change_status(version_id, payload, user.id)


@router.post("/{version_id}/publish")
def publish_version(
    version_id: int,
    payload: PublishVersionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).publish(version_id, payload, user.id)

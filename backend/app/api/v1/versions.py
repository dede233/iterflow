from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.repositories.version_repository import VersionRepository
from app.schemas.version import VersionCreate, VersionUpdate, VersionStatusChange, PublishVersionRequest
from app.services.version_service import VersionService

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("")
def list_versions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.view"))):
    items, total = VersionRepository(db).list(page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("")
def create_version(payload: VersionCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.create"))):
    return VersionService(db).create(payload, user.id)


@router.get("/{version_id}")
def get_version(version_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.view"))):
    return VersionRepository(db).get(version_id)


@router.patch("/{version_id}")
def update_version(version_id: int, payload: VersionUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.edit"))):
    return VersionService(db).update(version_id, payload, user.id)


@router.patch("/{version_id}/status")
def change_version_status(version_id: int, payload: VersionStatusChange, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.status"))):
    return VersionService(db).change_status(version_id, payload, user.id)


@router.post("/{version_id}/publish")
def publish_version(version_id: int, payload: PublishVersionRequest, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.version.publish"))):
    return VersionService(db).publish(version_id, payload, user.id)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import User
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.requirement import (
    RequirementCreate,
    RequirementMoveVersion,
    RequirementStatusChange,
    RequirementUpdate,
)
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/requirements", tags=["requirements"])


def _scoped_requirement_or_404(db: Session, user: User, requirement_id: int):
    scope = UserRepository(db).data_scope(user.id)
    item = RequirementRepository(db).get_scoped(requirement_id, user.id, scope)
    if item is None:
        raise NotFoundError("需求不存在")
    return item


def _ensure_scoped_version(db: Session, user: User, version_id: int | None) -> None:
    if version_id is None:
        return
    scope = UserRepository(db).data_scope(user.id)
    if VersionRepository(db).get_scoped(version_id, user.id, scope) is None:
        raise NotFoundError("版本不存在")


@router.get("")
def list_requirements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    scope = UserRepository(db).data_scope(user.id)
    items, total = RequirementRepository(db).list_scoped(user.id, scope, page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("")
def create_requirement(
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.create")),
):
    _ensure_scoped_version(db, user, payload.version_id)
    return RequirementService(db).create(payload, user.id)


@router.get("/{requirement_id}")
def get_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    return _scoped_requirement_or_404(db, user, requirement_id)


@router.patch("/{requirement_id}")
def update_requirement(
    requirement_id: int,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementService(db).update(requirement_id, payload, user.id)


@router.patch("/{requirement_id}/status")
def change_status(
    requirement_id: int,
    payload: RequirementStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.status")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementService(db).change_status(requirement_id, payload, user.id)


@router.post("/{requirement_id}/move-version")
def move_version(
    requirement_id: int,
    payload: RequirementMoveVersion,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.version.move")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    _ensure_scoped_version(db, user, payload.target_version_id)
    return RequirementService(db).move_version(requirement_id, payload, user.id)

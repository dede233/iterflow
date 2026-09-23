from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_all_permissions, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.models.entities import User, Version
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.release import PublishCheckResult, PublishResult
from app.schemas.version import (
    AddRequirementRequest,
    MoveRequirementRequest,
    PublishVersionRequest,
    RemoveRequirementRequest,
    VersionCreate,
    VersionOut,
    VersionPage,
    VersionRequirementsOut,
    VersionStatusChange,
    VersionUpdate,
)
from app.services.publish_check_service import PublishCheckService
from app.services.version_service import VersionService

router = APIRouter(prefix="/versions", tags=["versions"])


def _scoped_version_or_404(db: Session, user: User, version_id: int) -> Version:
    scope = UserRepository(db).data_scope(user.id)
    item = VersionRepository(db).get_scoped(version_id, user.id, scope)
    if item is None:
        raise NotFoundError("版本不存在")
    return item


@router.get("", response_model=VersionPage)
def list_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    scope = UserRepository(db).data_scope(user.id)
    items, total = VersionRepository(db).list_scoped(user.id, scope, page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("", response_model=VersionOut)
def create_version(
    payload: VersionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.create")),
):
    return VersionService(db).create(payload, user.id)


@router.get("/{version_id}", response_model=VersionOut)
def get_version(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    return _scoped_version_or_404(db, user, version_id)


@router.patch("/{version_id}", response_model=VersionOut)
def update_version(
    version_id: int,
    payload: VersionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.edit")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).update(version_id, payload, user.id)


@router.patch("/{version_id}/status", response_model=VersionOut)
def change_version_status(
    version_id: int,
    payload: VersionStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.status")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).change_status(version_id, payload, user.id)


# --------------------------------------------------------------------------- #
# Version <-> Requirement relationship management (all through VersionService) #
# --------------------------------------------------------------------------- #
@router.get("/{version_id}/requirements", response_model=VersionRequirementsOut)
def list_version_requirements(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.version.view", "rd.requirement.view")),
):
    _scoped_version_or_404(db, user, version_id)
    scope = UserRepository(db).data_scope(user.id)
    requirements, stats = VersionService(db).requirements_view(version_id, user.id, scope)
    return {"version_id": version_id, "stats": stats, "items": requirements}


@router.post("/{version_id}/requirements", response_model=VersionOut)
def add_version_requirement(
    version_id: int,
    payload: AddRequirementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.version.edit", "rd.requirement.view")),
):
    _scoped_version_or_404(db, user, version_id)
    scope = UserRepository(db).data_scope(user.id)
    return VersionService(db).add_requirement(
        version_id, payload, user.id, viewer_scope=scope, viewer_id=user.id
    )


@router.post("/{version_id}/requirements/move", response_model=VersionOut)
def move_version_requirement(
    version_id: int,
    payload: MoveRequirementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.version.edit", "rd.requirement.view")),
):
    _scoped_version_or_404(db, user, version_id)
    scope = UserRepository(db).data_scope(user.id)
    return VersionService(db).move_requirement(
        version_id, payload, user.id, viewer_scope=scope, viewer_id=user.id
    )


@router.delete("/{version_id}/requirements/{requirement_id}", response_model=VersionOut)
def remove_version_requirement(
    version_id: int,
    requirement_id: int,
    payload: RemoveRequirementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.version.edit", "rd.requirement.view")),
):
    _scoped_version_or_404(db, user, version_id)
    scope = UserRepository(db).data_scope(user.id)
    return VersionService(db).remove_requirement(
        version_id,
        requirement_id,
        payload,
        user.id,
        viewer_scope=scope,
        viewer_id=user.id,
    )


@router.post("/{version_id}/publish/check", response_model=PublishCheckResult)
def check_version_publish(
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    version = _scoped_version_or_404(db, user, version_id)
    result = PublishCheckService(db).evaluate(version)
    if not result["passed"]:
        raise AppError(
            40923,
            "发布检查未通过",
            409,
            {
                "checks": result["checks"],
                "blocking_requirements": PublishCheckService.blocking_requirements(result),
            },
        )
    return result


@router.post("/{version_id}/publish", response_model=PublishResult)
def publish_version(
    version_id: int,
    payload: PublishVersionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).publish(version_id, payload, user.id)

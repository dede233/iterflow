from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.api.deps import require_all_permissions, require_permission
from app.api.openapi import api_error_responses, api_revision_conflict_responses
from app.core.database import get_db
from app.core.exceptions import AppError, NotFoundError
from app.models.entities import User, Version
from app.models.enums import VersionStatus
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


@router.get(
    "",
    response_model=VersionPage,
    description=(
        "所有筛选条件与 Version DataScope 使用 AND 组合。列表与 total 使用相同条件。"
        "keyword trim 后按版本号/名称做大小写不敏感的部分匹配。空白视为无筛选。"
        "计划发布日期范围包含两端。可只指定一端。from 晚于 to 返回 validation 422。"
        "owner_id 只按版本字段过滤。不要求额外 User 权限。"
    ),
)
def list_versions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=200),
    status: VersionStatus | None = Query(None),
    planned_release_from: date | None = Query(None),
    planned_release_to: date | None = Query(None),
    owner_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.view")),
):
    if planned_release_from and planned_release_to and planned_release_from > planned_release_to:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "planned_release_to"),
                    "msg": "计划上线结束日期不能早于开始日期",
                    "input": planned_release_to.isoformat(),
                }
            ]
        )
    scope = UserRepository(db).data_scope(user.id)
    items, total = VersionRepository(db).list_scoped(
        user.id,
        scope,
        page,
        page_size,
        keyword=keyword,
        status=status,
        planned_release_from=planned_release_from,
        planned_release_to=planned_release_to,
        owner_id=owner_id,
    )
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


@router.patch(
    "/{version_id}", response_model=VersionOut, responses=api_revision_conflict_responses(404, 409)
)
def update_version(
    version_id: int,
    payload: VersionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.edit")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).update(version_id, payload, user.id)


@router.patch(
    "/{version_id}/status",
    response_model=VersionOut,
    responses=api_revision_conflict_responses(404, 409),
)
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


@router.post(
    "/{version_id}/requirements",
    response_model=VersionOut,
    responses=api_revision_conflict_responses(404, 409),
)
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


@router.post(
    "/{version_id}/requirements/move",
    response_model=VersionOut,
    responses=api_revision_conflict_responses(404, 409),
)
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


@router.delete(
    "/{version_id}/requirements/{requirement_id}",
    response_model=VersionOut,
    responses=api_revision_conflict_responses(404, 409),
)
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


@router.post(
    "/{version_id}/publish/check",
    response_model=PublishCheckResult,
    responses=api_error_responses(404, 409),
)
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


@router.post(
    "/{version_id}/publish",
    response_model=PublishResult,
    responses=api_revision_conflict_responses(404, 409),
)
def publish_version(
    version_id: int,
    payload: PublishVersionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    _scoped_version_or_404(db, user, version_id)
    return VersionService(db).publish(version_id, payload, user.id)

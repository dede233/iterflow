from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import require_any_permission, require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.target_release import (
    ReleaseBatchAdjust,
    ReleaseBatchCancel,
    ReleaseBatchCreate,
    ReleaseBatchesOut,
    ReleaseBatchOut,
    ReleaseCoverageCreate,
    ReleaseTargetComplete,
    ReleaseTargetCreate,
    ReleaseTargetOut,
    ReleaseTargetUpdate,
    TargetReleaseOption,
    TargetReleasePage,
)
from app.services.target_release_service import TargetReleaseService

router = APIRouter(tags=["TargetRelease"])
reader = require_any_permission("rd.version.view", "rd.version.publish", "rd.release.view")
errors = api_error_responses(404, 409)


@router.get(
    "/systems/{system_id}/release-targets", response_model=list[ReleaseTargetOut], responses=errors
)
def catalog(
    system_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.system.manage")),
):
    return TargetReleaseService(db).catalog(system_id, user.id)


@router.post(
    "/systems/{system_id}/release-targets",
    response_model=ReleaseTargetOut,
    status_code=201,
    responses=errors,
)
def create_target(
    payload: ReleaseTargetCreate,
    system_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.system.manage")),
):
    return TargetReleaseService(db).create_target(system_id, payload, user.id)


@router.patch(
    "/systems/release-targets/{target_id}", response_model=ReleaseTargetOut, responses=errors
)
def update_target(
    payload: ReleaseTargetUpdate,
    target_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.system.manage")),
):
    return TargetReleaseService(db).update_target(target_id, payload, user.id)


@router.get(
    "/versions/{version_id}/release-targets",
    response_model=list[ReleaseTargetOut],
    responses=errors,
)
def target_options(
    version_id: int = Path(ge=1),
    system_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(reader),
):
    return TargetReleaseService(db).target_options(version_id, user.id, system_id)


@router.get(
    "/versions/{version_id}/release-batches", response_model=ReleaseBatchesOut, responses=errors
)
def batches(
    version_id: int = Path(ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(reader),
):
    return TargetReleaseService(db).listing(version_id, user.id, page, page_size)


@router.post(
    "/versions/{version_id}/release-batches",
    response_model=ReleaseBatchOut,
    status_code=201,
    responses=errors,
)
def create_batch(
    payload: ReleaseBatchCreate,
    version_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    return TargetReleaseService(db).create_batch(version_id, payload, user.id)


@router.post(
    "/versions/{version_id}/release-coverage",
    response_model=ReleaseBatchOut,
    status_code=201,
    responses=errors,
)
def record_coverage(
    payload: ReleaseCoverageCreate,
    version_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    return TargetReleaseService(db).record_coverage(version_id, payload, user.id)


@router.patch(
    "/versions/{version_id}/release-batches/{batch_id}/targets",
    response_model=ReleaseBatchOut,
    responses=errors,
)
def adjust_batch(
    payload: ReleaseBatchAdjust,
    version_id: int = Path(ge=1),
    batch_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    return TargetReleaseService(db).edit_batch(version_id, batch_id, payload, user.id)


@router.post(
    "/versions/{version_id}/release-batches/{batch_id}/cancel",
    response_model=ReleaseBatchOut,
    responses=errors,
)
def cancel_batch(
    payload: ReleaseBatchCancel,
    version_id: int = Path(ge=1),
    batch_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    return TargetReleaseService(db).edit_batch(version_id, batch_id, payload, user.id, cancel=True)


@router.post(
    "/versions/{version_id}/release-batches/{batch_id}/targets/{batch_target_id}/complete",
    response_model=ReleaseBatchOut,
    responses=errors,
)
def complete_target(
    payload: ReleaseTargetComplete,
    version_id: int = Path(ge=1),
    batch_id: int = Path(ge=1),
    batch_target_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.version.publish")),
):
    return TargetReleaseService(db).complete(
        version_id, batch_id, batch_target_id, payload, user.id
    )


@router.get("/target-release-records", response_model=TargetReleasePage, responses=errors)
def target_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    target_id: int | None = Query(None, ge=1),
    version_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.release.view")),
):
    return TargetReleaseService(db).records(user.id, page, page_size, target_id, version_id)


@router.get(
    "/target-release-records/options", response_model=list[TargetReleaseOption], responses=errors
)
def record_options(
    db: Session = Depends(get_db), user: User = Depends(require_permission("rd.release.view"))
):
    return TargetReleaseService(db).record_options(user.id)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_all_data_scope, require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.system import (
    BusinessModuleCreate,
    BusinessModuleOut,
    BusinessModuleUpdate,
    BusinessSystemCatalogOut,
    BusinessSystemCreate,
    BusinessSystemOut,
    BusinessSystemUpdate,
)
from app.services.system_catalog_service import SystemCatalogService
from app.services.system_query_service import SystemQueryService

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("", response_model=BusinessSystemCatalogOut)
def list_systems(
    db: Session = Depends(get_db), user: User = Depends(require_permission("sys.system.view"))
):
    return SystemQueryService(db).list_enabled()


@router.get(
    "/manage",
    response_model=BusinessSystemCatalogOut,
    description="需要 sys.system.manage 与 ALL 数据范围; 包含已停用的系统与模块。",
)
def list_all_systems(
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.system.manage")),
):
    require_all_data_scope(current, db)
    return SystemCatalogService(db).list_all()


@router.post(
    "",
    response_model=BusinessSystemOut,
    status_code=201,
    responses=api_error_responses(409),
    description="需要 sys.system.manage 与 ALL 数据范围; 创建和审计在同一事务中完成。",
)
def create_system(
    payload: BusinessSystemCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.system.manage")),
):
    require_all_data_scope(current, db)
    return SystemCatalogService(db).create_system(payload, current.id)


@router.patch(
    "/{system_id}",
    response_model=BusinessSystemOut,
    responses=api_error_responses(404, 409),
    description="需要 sys.system.manage 与 ALL 数据范围; 携带 revision, 停用保留历史关联。",
)
def update_system(
    system_id: int,
    payload: BusinessSystemUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.system.manage")),
):
    require_all_data_scope(current, db)
    return SystemCatalogService(db).update_system(system_id, payload, current.id)


@router.post(
    "/{system_id}/modules",
    response_model=BusinessModuleOut,
    status_code=201,
    responses=api_error_responses(404, 409),
    description="需要 sys.system.manage 与 ALL 数据范围。",
)
def create_module(
    system_id: int,
    payload: BusinessModuleCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.system.manage")),
):
    require_all_data_scope(current, db)
    return SystemCatalogService(db).create_module(system_id, payload, current.id)


@router.patch(
    "/modules/{module_id}",
    response_model=BusinessModuleOut,
    responses=api_error_responses(404, 409),
    description="需要 sys.system.manage 与 ALL 数据范围; 携带 revision, 停用保留历史关联。",
)
def update_module(
    module_id: int,
    payload: BusinessModuleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.system.manage")),
):
    require_all_data_scope(current, db)
    return SystemCatalogService(db).update_module(module_id, payload, current.id)

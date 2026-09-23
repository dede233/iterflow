from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_all_data_scope, require_permission
from app.core.database import get_db
from app.models.entities import User
from app.schemas.role import (
    PermissionOut,
    RoleCreate,
    RoleDeleteOut,
    RoleOut,
    RolePermissionUpdate,
    RoleUpdate,
)
from app.services.role_management_service import RoleManagementService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).list()


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).list_permissions()


@router.get("/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.view")),
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).get(role_id)


@router.post("", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.manage")),
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).create(payload, current.id)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.manage")),
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).update(role_id, payload, current.id)


@router.put("/{role_id}/permissions", response_model=RoleOut)
def update_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.manage")),
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).update_permissions(role_id, payload, current.id)


@router.delete("/{role_id}", response_model=RoleDeleteOut)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.manage")),
):
    require_all_data_scope(current, db)
    return RoleManagementService(db).delete(role_id, current.id)

from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import Permission, Role, RolePermission, User
from app.schemas.role import RoleCreate, RoleOut, RolePermissionUpdate, RoleUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("")
def list_roles(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    return db.scalars(select(Role).order_by(Role.id)).all()


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    return db.scalars(select(Permission).order_by(Permission.code)).all()


@router.post("", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    role = Role(
        code=payload.code,
        name=payload.name,
        data_scope=payload.data_scope,
        created_by=current.id,
        updated_by=current.id,
    )
    db.add(role)
    db.flush()
    for pid in payload.permission_ids:
        db.add(RolePermission(role_id=role.id, permission_id=pid))
    AuditService(db).log(
        "ROLE",
        role.id,
        "CREATE",
        after={"code": role.code, "permission_ids": payload.permission_ids},
    )
    db.commit()
    db.refresh(role)
    return role


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    role = db.get(Role, role_id)
    if role is None:
        raise NotFoundError("角色不存在")

    before = {
        "code": role.code,
        "name": role.name,
        "data_scope": role.data_scope,
        "enabled": role.enabled,
    }
    values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
    values["updated_by"] = current.id
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Role)
            .where(Role.id == role_id, Role.revision == payload.revision)
            .values(**values, revision=Role.revision + 1)
        ),
    )
    if not result.rowcount:
        db.refresh(role)
        raise ConflictError("角色已被其他用户修改", {"current_revision": role.revision})

    AuditService(db).log(
        "ROLE",
        role_id,
        "UPDATE",
        before=before,
        after=values,
    )
    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}/permissions")
def update_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    role = db.get(Role, role_id)
    if not role:
        return None
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Role)
            .where(Role.id == role_id, Role.revision == payload.revision)
            .values(updated_by=current.id, revision=Role.revision + 1)
        ),
    )
    if not result.rowcount:
        db.refresh(role)
        raise ConflictError("角色权限已被其他用户修改", {"current_revision": role.revision})
    db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for pid in payload.permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))
    AuditService(db).log(
        "ROLE",
        role_id,
        "PERMISSIONS_UPDATE",
        after={"permission_ids": payload.permission_ids},
    )
    db.commit()
    db.refresh(role)
    return {"ok": True, "revision": role.revision}

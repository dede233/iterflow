from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.api.deps import require_all_data_scope, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.models.entities import Permission, Role, RolePermission, User
from app.schemas.role import PermissionOut, RoleCreate, RoleOut, RolePermissionUpdate, RoleUpdate
from app.services.audit_service import AuditService

router = APIRouter(prefix="/roles", tags=["roles"])


def _role_out(db: Session, role: Role) -> RoleOut:
    permission_ids = list(
        db.scalars(
            select(RolePermission.permission_id)
            .where(RolePermission.role_id == role.id)
            .order_by(RolePermission.permission_id)
        ).all()
    )
    return RoleOut.model_validate(role).model_copy(update={"permission_ids": permission_ids})


def _validate_permission_ids(db: Session, permission_ids: list[int]) -> None:
    if not permission_ids:
        return
    found_ids = set(
        db.scalars(select(Permission.id).where(Permission.id.in_(permission_ids))).all()
    )
    missing_ids = sorted(set(permission_ids) - found_ids)
    if missing_ids:
        raise AppError(42201, "包含不存在的权限", 422, {"permission_ids": missing_ids})


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    require_all_data_scope(current, db)
    return [_role_out(db, role) for role in db.scalars(select(Role).order_by(Role.id)).all()]


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db), current: User = Depends(require_permission("sys.role.view"))
):
    require_all_data_scope(current, db)
    return db.scalars(select(Permission).order_by(Permission.code)).all()


@router.post("", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    require_all_data_scope(current, db)
    _validate_permission_ids(db, payload.permission_ids)
    if db.scalar(select(Role.id).where(Role.code == payload.code)) is not None:
        raise ConflictError("角色编码已存在")
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
    return _role_out(db, role)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    require_all_data_scope(current, db)
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
    if "code" in values:
        same_code_role = db.scalar(select(Role.id).where(Role.code == values["code"]))
        if same_code_role is not None and same_code_role != role_id:
            raise ConflictError("角色编码已存在")
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
    return _role_out(db, role)


@router.put("/{role_id}/permissions", response_model=RoleOut)
def update_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.role.edit")),
):
    require_all_data_scope(current, db)
    role = db.get(Role, role_id)
    if not role:
        raise NotFoundError("角色不存在")
    _validate_permission_ids(db, payload.permission_ids)
    before_permission_ids = list(
        db.scalars(
            select(RolePermission.permission_id)
            .where(RolePermission.role_id == role_id)
            .order_by(RolePermission.permission_id)
        ).all()
    )
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
        before={"permission_ids": before_permission_ids},
        after={"permission_ids": payload.permission_ids},
    )
    db.commit()
    db.refresh(role)
    return _role_out(db, role)

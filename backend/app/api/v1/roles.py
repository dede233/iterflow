from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import ConflictError
from app.models.entities import User, Role, Permission, RolePermission
from app.schemas.role import RoleCreate, RolePermissionUpdate

router=APIRouter(prefix="/roles",tags=["roles"])


@router.get("")
def list_roles(db:Session=Depends(get_db), current:User=Depends(require_permission("sys.role.view"))):
    return db.scalars(select(Role).order_by(Role.id)).all()


@router.get("/permissions")
def list_permissions(db:Session=Depends(get_db), current:User=Depends(require_permission("sys.role.view"))):
    return db.scalars(select(Permission).order_by(Permission.code)).all()


@router.post("")
def create_role(payload:RoleCreate, db:Session=Depends(get_db), current:User=Depends(require_permission("sys.role.edit"))):
    role=Role(code=payload.code,name=payload.name,data_scope=payload.data_scope,created_by=current.id,updated_by=current.id)
    db.add(role);db.flush()
    for pid in payload.permission_ids: db.add(RolePermission(role_id=role.id,permission_id=pid))
    db.commit();db.refresh(role);return role


@router.put("/{role_id}/permissions")
def update_permissions(role_id:int,payload:RolePermissionUpdate,db:Session=Depends(get_db),current:User=Depends(require_permission("sys.role.edit"))):
    role=db.get(Role,role_id)
    if not role:return None
    if role.revision!=payload.revision: raise ConflictError("角色权限已被其他用户修改",{"current_revision":role.revision})
    db.execute(delete(RolePermission).where(RolePermission.role_id==role_id))
    for pid in payload.permission_ids: db.add(RolePermission(role_id=role_id,permission_id=pid))
    role.revision+=1;role.updated_by=current.id;db.commit();return {"ok":True,"revision":role.revision}

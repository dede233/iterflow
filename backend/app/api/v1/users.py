from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.api.deps import require_all_data_scope, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.core.security import hash_password
from app.models.entities import Role, User, UserRole
from app.models.enums import DataScope, UserStatus
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreate,
    UserOut,
    UserPage,
    UserRoleUpdate,
    UserStatusChange,
    UserUpdate,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])


def _user_out(repository: UserRepository, user: User) -> UserOut:
    return UserOut.model_validate(user).model_copy(
        update={"role_ids": repository.role_ids(user.id)}
    )


def _user_page_out(repository: UserRepository, users: list[User]) -> list[UserOut]:
    role_ids_by_user = repository.role_ids_by_user([item.id for item in users])
    return [
        UserOut.model_validate(item).model_copy(
            update={"role_ids": role_ids_by_user.get(item.id, [])}
        )
        for item in users
    ]


def _validate_role_ids(db: Session, role_ids: list[int]) -> None:
    if not role_ids:
        return
    rows = db.execute(select(Role.id, Role.enabled).where(Role.id.in_(role_ids))).all()
    found_ids = {role_id for role_id, _enabled in rows}
    disabled_ids = sorted(role_id for role_id, enabled in rows if not enabled)
    missing_ids = sorted(set(role_ids) - found_ids)
    if missing_ids:
        raise AppError(42202, "包含不存在的角色", 422, {"role_ids": missing_ids})
    if disabled_ids:
        raise AppError(42203, "不能分配已禁用的角色", 422, {"role_ids": disabled_ids})


def _get_user_in_scope(repository: UserRepository, user_id: int, current: User) -> User:
    data_scope = repository.data_scope(current.id)
    if data_scope is not DataScope.ALL and user_id != current.id:
        raise PermissionDenied("无权访问其他用户的账号信息")
    item = repository.get(user_id)
    if item is None:
        raise NotFoundError("用户不存在")
    return item


@router.get("", response_model=UserPage)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.view")),
):
    repository = UserRepository(db)
    items, total = repository.list_scoped(
        current.id,
        repository.data_scope(current.id),
        page=page,
        page_size=page_size,
    )
    return {
        "items": _user_page_out(repository, items),
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.view")),
):
    repository = UserRepository(db)
    return _user_out(repository, _get_user_in_scope(repository, user_id, current))


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.create")),
    _role_assigner: User = Depends(require_permission("sys.user.role.assign")),
):
    require_all_data_scope(current, db)
    repository = UserRepository(db)
    if repository.by_username(payload.username) is not None:
        raise ConflictError("用户名已存在")
    _validate_role_ids(db, payload.role_ids)

    item = User(
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        must_change_password=True,
        created_by=current.id,
        updated_by=current.id,
    )
    db.add(item)
    db.flush()
    for role_id in payload.role_ids:
        db.add(UserRole(user_id=item.id, role_id=role_id))
    AuditService(db).log(
        "USER",
        item.id,
        "CREATE",
        after={"username": item.username, "role_ids": payload.role_ids},
    )
    db.commit()
    db.refresh(item)
    return _user_out(repository, item)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.edit")),
):
    repository = UserRepository(db)
    item = _get_user_in_scope(repository, user_id, current)
    before = {
        "display_name": item.display_name,
        "email": item.email,
        "mobile": item.mobile,
    }
    values = payload.model_dump(exclude={"revision"}, exclude_unset=True)
    values["updated_by"] = current.id
    result = cast(
        CursorResult[Any],
        db.execute(
            update(User)
            .where(User.id == user_id, User.revision == payload.revision)
            .values(**values, revision=User.revision + 1)
        ),
    )
    if not result.rowcount:
        db.refresh(item)
        raise ConflictError("用户已被其他用户修改", {"current_revision": item.revision})
    AuditService(db).log("USER", user_id, "UPDATE", before=before, after=values)
    db.commit()
    db.refresh(item)
    return _user_out(repository, item)


@router.patch("/{user_id}/status", response_model=UserOut)
def set_status(
    user_id: int,
    payload: UserStatusChange,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.status")),
):
    require_all_data_scope(current, db)
    repository = UserRepository(db)
    item = repository.get(user_id)
    if item is None:
        raise NotFoundError("用户不存在")
    previous_status = item.status
    updated = cast(
        CursorResult[Any],
        db.execute(
            update(User)
            .where(User.id == user_id, User.revision == payload.revision)
            .values(
                status=payload.status,
                updated_by=current.id,
                revision=User.revision + 1,
            )
        ),
    )
    if not updated.rowcount:
        db.refresh(item)
        raise ConflictError("用户已被其他用户修改", {"current_revision": item.revision})
    revoked_sessions = 0
    if payload.status is not UserStatus.ACTIVE:
        revoked_sessions = AuthService(db).revoke_user_sessions(user_id, reason="USER_DISABLED")
    AuditService(db).log(
        "USER",
        user_id,
        "STATUS_CHANGE",
        before={"status": previous_status},
        after={"status": payload.status, "revoked_session_count": revoked_sessions},
    )
    db.commit()
    db.refresh(item)
    return _user_out(repository, item)


@router.put("/{user_id}/roles", response_model=UserOut)
def update_user_roles(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.role.assign")),
):
    require_all_data_scope(current, db)
    repository = UserRepository(db)
    item = repository.get(user_id)
    if item is None:
        raise NotFoundError("用户不存在")
    _validate_role_ids(db, payload.role_ids)
    before_role_ids = repository.role_ids(user_id)
    updated = cast(
        CursorResult[Any],
        db.execute(
            update(User)
            .where(User.id == user_id, User.revision == payload.revision)
            .values(updated_by=current.id, revision=User.revision + 1)
        ),
    )
    if not updated.rowcount:
        db.refresh(item)
        raise ConflictError("用户角色已被其他用户修改", {"current_revision": item.revision})
    db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for role_id in payload.role_ids:
        db.add(UserRole(user_id=user_id, role_id=role_id))
    AuditService(db).log(
        "USER",
        user_id,
        "ROLES_UPDATE",
        before={"role_ids": before_role_ids},
        after={"role_ids": payload.role_ids},
    )
    db.commit()
    db.refresh(item)
    return _user_out(repository, item)

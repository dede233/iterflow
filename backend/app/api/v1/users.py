from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_all_data_scope, require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.core.exceptions import NotFoundError, PermissionDenied
from app.models.entities import User
from app.models.enums import DataScope
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreate,
    UserOut,
    UserPage,
    UserRoleUpdate,
    UserStatusChange,
    UserUpdate,
)
from app.services.user_administration_service import UserAdministrationService

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


@router.get("/{user_id}", response_model=UserOut, responses=api_error_responses(404))
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.view")),
):
    repository = UserRepository(db)
    return _user_out(repository, _get_user_in_scope(repository, user_id, current))


@router.post(
    "",
    response_model=UserOut,
    responses=api_error_responses(
        403,
        409,
        descriptions={403: "授予 SUPER_ADMIN 角色需要当前操作人是有效的超级管理员。"},
    ),
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.create")),
    _role_assigner: User = Depends(require_permission("sys.user.role.assign")),
):
    require_all_data_scope(current, db)
    return UserAdministrationService(db).create(payload, current.id)


@router.patch("/{user_id}", response_model=UserOut, responses=api_error_responses(404, 409))
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.edit")),
):
    repository = UserRepository(db)
    _get_user_in_scope(repository, user_id, current)
    return UserAdministrationService(db).update_profile(user_id, payload, current.id)


@router.patch(
    "/{user_id}/status",
    response_model=UserOut,
    responses=api_error_responses(
        404,
        403,
        409,
        descriptions={
            403: "变更 SUPER_ADMIN 用户状态需要当前操作人是有效的超级管理员。",
            409: "不能移除最后一个有效的超级管理员。",
        },
    ),
)
def set_status(
    user_id: int,
    payload: UserStatusChange,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.status")),
):
    require_all_data_scope(current, db)
    return UserAdministrationService(db).set_status(user_id, payload, current.id)


@router.put(
    "/{user_id}/roles",
    response_model=UserOut,
    responses=api_error_responses(
        404,
        403,
        409,
        descriptions={
            403: "授予或撤销 SUPER_ADMIN 角色需要当前操作人是有效的超级管理员。",
            409: "不能移除最后一个有效的超级管理员。",
        },
    ),
)
def update_user_roles(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.role.assign")),
):
    require_all_data_scope(current, db)
    return UserAdministrationService(db).update_roles(user_id, payload, current.id)

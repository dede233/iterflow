from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.audit_context import set_audit_operator
from app.core.database import get_db
from app.core.exceptions import AppError, PermissionDenied
from app.core.security import decode_token
from app.models.entities import User
from app.models.enums import DataScope, UserStatus
from app.repositories.user_repository import UserRepository

bearer = HTTPBearer(auto_error=False)

_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset(
    {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }
)


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise AppError(40100, "请先登录", 401)
    payload = decode_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != UserStatus.ACTIVE:
        raise AppError(40103, "用户不可用", 401)
    # Middleware initializes the transport metadata. Rebind the identity only
    # after the token subject has resolved to an active database user.
    set_audit_operator(user.id)
    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_ALLOWED_PATHS:
        raise AppError(
            40310,
            "首次登录后必须先修改密码",
            403,
            {"must_change_password": True},
        )
    return user


def require_any_permission(*codes: str) -> Callable:
    if not codes:
        raise ValueError("at least one permission code is required")

    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        permissions = UserRepository(db).permission_codes(user.id)
        if "*" not in permissions and permissions.isdisjoint(codes):
            raise PermissionDenied()
        return user

    return checker


def require_permission(code: str) -> Callable:
    return require_any_permission(code)


def require_all_data_scope(user: User, db: Session) -> User:
    """Require an effective ALL scope for administrative cross-user operations."""
    if UserRepository(db).data_scope(user.id) is not DataScope.ALL:
        raise PermissionDenied("需要 ALL 数据范围")
    return user

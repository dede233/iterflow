from collections.abc import Callable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.exceptions import AppError, PermissionDenied
from app.core.security import decode_token
from app.models.entities import User
from app.repositories.user_repository import UserRepository

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise AppError(40100, "请先登录", 401)
    payload = decode_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "ACTIVE":
        raise AppError(40103, "用户不可用", 401)
    return user


def require_permission(code: str) -> Callable:
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        permissions = UserRepository(db).permission_codes(user.id)
        if "*" not in permissions and code not in permissions:
            raise PermissionDenied()
        return user
    return checker

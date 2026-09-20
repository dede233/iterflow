from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.enums import UserStatus
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login(self, username: str, password: str):
        user = self.users.by_username(username)
        if (
            not user
            or user.status != UserStatus.ACTIVE
            or not verify_password(password, user.password_hash)
        ):
            raise AppError(40110, "用户名或密码错误", 401)
        session_id = uuid4().hex
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id, session_id),
            "token_type": "bearer",
        }

    def refresh(self, refresh_token: str):
        payload = decode_token(refresh_token, "refresh")
        user_id = int(payload["sub"])
        session_id = payload.get("sid") or uuid4().hex
        return {
            "access_token": create_access_token(user_id),
            "refresh_token": create_refresh_token(user_id, session_id),
            "token_type": "bearer",
        }

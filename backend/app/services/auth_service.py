from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.audit_context import set_audit_operator
from app.core.config import get_settings
from app.core.exceptions import AppError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.entities import RefreshSession, User, UserRole
from app.models.enums import UserStatus
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    """Authentication and server-revocable refresh-session operations."""

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _new_refresh_session(self, user_id: int) -> RefreshSession:
        settings = get_settings()
        return RefreshSession(
            id=uuid4().hex,
            user_id=user_id,
            token_jti=uuid4().hex,
            expires_at=self._now() + timedelta(days=settings.jwt_refresh_ttl_days),
        )

    @staticmethod
    def _token_pair(user: User, refresh_session: RefreshSession) -> dict[str, Any]:
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(
                user.id,
                refresh_session.id,
                refresh_session.token_jti,
            ),
            "token_type": "bearer",
            "must_change_password": user.must_change_password,
        }

    @staticmethod
    def _invalid_login() -> NoReturn:
        raise AppError(40110, "用户名或密码错误", 401)

    @staticmethod
    def _invalid_refresh() -> NoReturn:
        raise AppError(40111, "刷新凭证无效或已失效", 401)

    def _audit_login_failure(self, username: str) -> None:
        # Usernames are identifiers rather than credentials. Passwords and
        # tokens never enter an OperationLog payload.
        AuditService(self.db).log(
            "AUTH",
            None,
            "LOGIN_FAILED",
            after={"username": username},
        )
        self.db.commit()

    @staticmethod
    def _refresh_claims(refresh_token: str) -> tuple[int, str, str]:
        payload = decode_token(refresh_token, "refresh")
        try:
            user_id = int(payload["sub"])
            session_id = payload["sid"]
            token_jti = payload["jti"]
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError(40111, "刷新凭证无效或已失效", 401) from exc
        if (
            not isinstance(session_id, str)
            or not isinstance(token_jti, str)
            or len(session_id) != 32
            or len(token_jti) != 32
        ):
            raise AppError(40111, "刷新凭证无效或已失效", 401)
        return user_id, session_id, token_jti

    @staticmethod
    def _session_expired(refresh_session: RefreshSession, now: datetime) -> bool:
        """Compare timestamps safely with SQLite test databases.

        PostgreSQL preserves timezone information for ``TIMESTAMPTZ``. SQLite
        intentionally does not, so test and local lightweight integrations may
        return a naive datetime for the same UTC value.
        """

        expires_at = refresh_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= now

    def _matching_refresh_session(
        self, refresh_token: str, *, require_active: bool
    ) -> tuple[RefreshSession, User, str]:
        user_id, session_id, token_jti = self._refresh_claims(refresh_token)
        refresh_session = self.db.get(RefreshSession, session_id)
        user = self.db.get(User, user_id)
        now = self._now()
        if (
            refresh_session is None
            or user is None
            or refresh_session.user_id != user_id
            or refresh_session.token_jti != token_jti
            or self._session_expired(refresh_session, now)
            or (require_active and refresh_session.revoked_at is not None)
        ):
            self._invalid_refresh()
        return refresh_session, user, token_jti

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self.users.by_username(username)
        if (
            not user
            or user.status != UserStatus.ACTIVE
            or not verify_password(password, user.password_hash)
        ):
            self._audit_login_failure(username)
            self._invalid_login()

        set_audit_operator(user.id)
        refresh_session = self._new_refresh_session(user.id)
        user.last_login_at = self._now()
        self.db.add(refresh_session)
        AuditService(self.db).log(
            "AUTH",
            user.id,
            "LOGIN",
            after={"username": user.username},
        )
        self.db.commit()
        return self._token_pair(user, refresh_session)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        refresh_session, user, token_jti = self._matching_refresh_session(
            refresh_token, require_active=True
        )
        if user.status != UserStatus.ACTIVE:
            self._invalid_refresh()

        now = self._now()
        replacement = self._new_refresh_session(user.id)
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.id == refresh_session.id,
                    RefreshSession.token_jti == token_jti,
                    RefreshSession.revoked_at.is_(None),
                    RefreshSession.expires_at > now,
                )
                .values(
                    revoked_at=now,
                    revoked_reason="REFRESHED",
                    last_used_at=now,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        if not result.rowcount:
            self.db.rollback()
            self._invalid_refresh()

        self.db.add(replacement)
        self.db.expire(refresh_session)
        self.db.commit()
        return self._token_pair(user, replacement)

    def logout(self, refresh_token: str) -> dict[str, bool]:
        refresh_session, user, token_jti = self._matching_refresh_session(
            refresh_token, require_active=False
        )
        if refresh_session.revoked_at is not None:
            return {"ok": True}

        now = self._now()
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.id == refresh_session.id,
                    RefreshSession.token_jti == token_jti,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=now, revoked_reason="LOGOUT", last_used_at=now)
            ),
        )
        if result.rowcount:
            set_audit_operator(user.id)
            AuditService(self.db).log("AUTH", user.id, "LOGOUT")
            self.db.commit()
        return {"ok": True}

    def revoke_user_sessions(self, user_id: int, reason: str) -> int:
        """Revoke every active refresh session in the caller's transaction.

        This deliberately does not commit. User status, role, and password
        changes can therefore revoke sessions atomically with their own audit
        writes.
        """

        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(RefreshSession)
                .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
                .values(revoked_at=self._now(), revoked_reason=reason[:64])
            ),
        )
        return int(result.rowcount or 0)

    def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> dict[str, Any]:
        set_audit_operator(user.id)
        if not verify_password(current_password, user.password_hash):
            AuditService(self.db).log("AUTH", user.id, "PASSWORD_CHANGE_FAILED")
            self.db.commit()
            raise AppError(40112, "当前密码错误", 401)

        before_must_change_password = user.must_change_password
        result = cast(
            CursorResult[Any],
            self.db.execute(
                update(User)
                .where(
                    User.id == user.id,
                    User.status == UserStatus.ACTIVE,
                    User.password_hash == user.password_hash,
                )
                .values(
                    password_hash=hash_password(new_password),
                    must_change_password=False,
                    updated_by=user.id,
                    revision=User.revision + 1,
                )
            ),
        )
        if not result.rowcount:
            self.db.rollback()
            raise ConflictError("密码已被其他操作修改; 请重新登录")

        self.revoke_user_sessions(user.id, "PASSWORD_CHANGED")
        refresh_session = self._new_refresh_session(user.id)
        self.db.add(refresh_session)
        AuditService(self.db).log(
            "AUTH",
            user.id,
            "PASSWORD_CHANGE",
            before={"must_change_password": before_must_change_password},
            after={"must_change_password": False},
        )
        self.db.commit()
        self.db.refresh(user)
        return self._token_pair(user, refresh_session)

    def me(self, user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "status": user.status,
            "revision": user.revision,
            "must_change_password": user.must_change_password,
            "data_scope": self.users.data_scope(user.id),
            "role_ids": list(
                self.db.scalars(
                    select(UserRole.role_id)
                    .where(UserRole.user_id == user.id)
                    .order_by(UserRole.role_id)
                ).all()
            ),
            "permission_codes": sorted(self.users.permission_codes(user.id)),
        }

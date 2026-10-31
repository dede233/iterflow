import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, ConflictError
from app.models.entities import CollaborationEvent, MailPreference, User
from app.schemas.mail import MailMode, MailPreferencesOut
from app.services.audit_service import AuditService


def verification_code(challenge_id: str) -> str:
    digest = hmac.new(
        get_settings().jwt_secret.get_secret_value().encode(),
        f"mail:{challenge_id}".encode(),
        hashlib.sha256,
    ).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1000000:06d}"


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class MailPreferencesService:
    def __init__(self, db: Session):
        self.db = db

    def lock(self, user: User, revision: int | None = None) -> MailPreference:
        self.db.refresh(user, with_for_update=True)
        item = self.db.scalar(
            select(MailPreference).where(MailPreference.user_id == user.id).with_for_update()
        )
        if item is None:
            item = MailPreference(user_id=user.id)
            self.db.add(item)
            self.db.flush()
        if revision is not None and item.revision != revision:
            raise ConflictError("邮件设置已修改, 请刷新", {"current_revision": item.revision})
        return item

    def view(self, user: User, item: MailPreference) -> MailPreferencesOut:
        return MailPreferencesOut(
            revision=item.revision,
            mode=cast(MailMode, item.mode),
            email=user.email,
            verified=bool(user.email and item.verified_email == user.email),
            pending_email=item.pending_email,
            smtp_enabled=get_settings().smtp_enabled,
        )

    def get(self, user: User):
        item = self.lock(user)
        self.db.commit()
        return self.view(user, item)

    def change(self, user: User, revision: int, mode: str):
        item = self.lock(user, revision)
        item.mode = mode
        item.revision += 1
        AuditService(self.db).log("USER", user.id, "MAIL_PREFERENCE", after={"mode": mode})
        self.db.commit()
        return self.view(user, item)

    def request(self, user: User, revision: int, email: str):
        if not get_settings().smtp_enabled:
            raise AppError(40970, "邮件服务尚未启用", 409)
        item = self.lock(user, revision)
        now = datetime.now(UTC)
        if item.requested_at and aware(item.requested_at) > now - timedelta(seconds=60):
            raise AppError(42970, "请等待一分钟后再发送验证码", 429)
        item.pending_email = email
        item.challenge_id = str(uuid4())
        item.challenge_expires_at = now + timedelta(minutes=15)
        item.challenge_user_revision = user.revision
        item.challenge_attempts = 0
        item.requested_at = now
        item.revision += 1
        self.db.add(
            CollaborationEvent(
                id=item.challenge_id,
                entity_type="ACCOUNT",
                entity_id=user.id,
                action="VERIFY_EMAIL",
                actor_id=user.id,
                recipient_ids=[user.id],
            )
        )
        AuditService(self.db).log("USER", user.id, "EMAIL_VERIFICATION_REQUEST")
        self.db.commit()
        return self.view(user, item)

    def confirm(self, user: User, revision: int, code: str):
        item = self.lock(user, revision)
        if (
            not item.challenge_id
            or not item.challenge_expires_at
            or aware(item.challenge_expires_at) < datetime.now(UTC)
            or item.challenge_attempts >= 5
            or item.challenge_user_revision != user.revision
        ):
            raise AppError(40970, "验证码已失效, 请重新发送", 409)
        if not hmac.compare_digest(code, verification_code(item.challenge_id)):
            item.challenge_attempts += 1
            self.db.commit()
            raise AppError(42270, "验证码不正确", 422)
        user.email = item.pending_email
        user.revision += 1
        user.updated_by = user.id
        item.verified_at = datetime.now(UTC)
        item.verified_email = item.pending_email
        item.pending_email = None
        item.challenge_id = None
        item.challenge_expires_at = None
        item.revision += 1
        AuditService(self.db).log("USER", user.id, "EMAIL_VERIFIED")
        self.db.commit()
        return self.view(user, item)

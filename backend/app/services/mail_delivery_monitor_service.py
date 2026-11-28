import hmac
import re
from datetime import UTC, datetime

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDenied
from app.models.entities import CollaborationEvent, MailPreference, NotificationDelivery, User
from app.models.enums import DataScope, UserStatus
from app.repositories.mail_delivery_repository import (
    RESENDABLE_MAIL_STATUSES,
    MailDeliveryRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.mail import (
    MailAddress,
    MailDeliveryDetail,
    MailDeliveryItem,
    MailDeliveryKind,
    MailDeliveryPage,
    MailDeliveryRecipient,
    MailDeliveryRecipientPage,
    MailDeliveryStatus,
)
from app.services.audit_service import AuditService
from app.services.delivery_service import ACTION_LABELS, DeliveryService
from app.services.mail_preferences_service import aware

_RECIPIENT_BLOCK_REASONS = {
    "EMAIL_ADDRESS_CHANGED": "接收人当前邮箱与该邮件排队时的地址不同",
    "EMAIL_NOT_CONFIGURED": "接收人尚未配置通知邮箱",
    "EMAIL_NOT_VERIFIED": "接收人尚未验证当前邮箱",
    "EVENT_BEFORE_EMAIL_VERIFICATION": "原事件发生在接收人验证当前邮箱之前",
    "EMAIL_NOTIFICATIONS_OFF": "接收人已关闭业务邮件通知",
    "EMAIL_NOT_A_TASK": "接收人仅接收待办邮件。原事件不属于待办",
    "VERIFICATION_EXPIRED_OR_REPLACED": "验证码已失效或已被替换。请重新发起验证",
    "SMTP_DISABLED": "邮件服务尚未启用",
    "NOT_ALLOWLISTED": "接收邮箱不在当前环境的发送许可名单中",
}
_SAFE_ERROR_CODES = frozenset(
    {
        *_RECIPIENT_BLOCK_REASONS,
        "ACCESS_REVOKED",
        "PREFERENCE_OR_EMAIL_CHANGED",
        "RETRY_LIMIT",
        "SMTP_CONNECTION_ERROR",
        "SMTP_OUTCOME_UNCERTAIN",
        "SMTP_RECIPIENT_REFUSED",
    }
)
_SCHEDULED_STATUSES = frozenset(
    {MailDeliveryStatus.PENDING, MailDeliveryStatus.RETRY, MailDeliveryStatus.UNCERTAIN}
)
_MAIL_ADDRESS = TypeAdapter(MailAddress)
_RESEND_PERMISSION_MESSAGE = "仅启用的内置超级管理员可重发邮件"
_STATUS_BLOCK_REASONS = {
    MailDeliveryStatus.PENDING: "邮件已在等待发送",
    MailDeliveryStatus.SENDING: "邮件正在发送",
    MailDeliveryStatus.RETRY: "邮件正在等待自动重试",
    MailDeliveryStatus.SKIPPED: "已跳过的邮件不可重发",
    MailDeliveryStatus.UNCERTAIN: "上次发送结果未确定。后台将按原计划处理",
}


def _safe_error_code(value: str | None) -> str | None:
    if value is None or value in _SAFE_ERROR_CODES or re.fullmatch(r"SMTP_[45][0-9]{2}", value):
        return value
    return "UNKNOWN"


def _mask_email(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        address = _MAIL_ADDRESS.validate_python(value)
    except ValidationError:
        return None
    local, domain = address.split("@")
    masked_local = f"{local[0]}***" if len(local) > 1 else "***"
    if masked_local == local:
        masked_local = "***"
    return f"{masked_local}@{domain}"


def _mail_kind(event_action: str) -> MailDeliveryKind:
    if event_action == "VERIFY_EMAIL":
        return MailDeliveryKind.EMAIL_VERIFICATION
    return MailDeliveryKind.COLLABORATION


def _safe_event_label(action: str) -> str:
    label = ACTION_LABELS.get(action.removeprefix("REQUIREMENT_"))
    if label is None:
        return "协作通知"
    if action.startswith("REQUIREMENT_"):
        return f"关联需求有新进展 · {label}"
    return label


def _next_attempt_at(delivery: NotificationDelivery) -> datetime | None:
    if delivery.status in _SCHEDULED_STATUSES:
        return aware(delivery.next_attempt_at).astimezone(UTC)
    return None


def _resend_token(delivery: NotificationDelivery, generation: int | None, actor_id: int) -> str:
    lease = aware(delivery.next_attempt_at).astimezone(UTC).isoformat()
    state = (
        f"mail-resend:{actor_id}:{delivery.id}:{delivery.status}:{delivery.attempts}:"
        f"{lease}:{generation}"
    )
    return hmac.digest(
        get_settings().jwt_secret.get_secret_value().encode(), state.encode(), "sha256"
    ).hex()


class MailDeliveryMonitorService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.deliveries = MailDeliveryRepository(db)
        self.sender = DeliveryService(db)

    def _require_access(self, user: User) -> None:
        if not self.users.can_view_mail_deliveries(user.id):
            raise PermissionDenied("无权查看全局邮件投递记录")

    def _can_resend(self, user: User) -> bool:
        return user.status == UserStatus.ACTIVE and self.users.has_enabled_builtin_super_admin_role(
            user.id
        )

    def _recipient_block_reason(
        self,
        row: NotificationDelivery,
        event: CollaborationEvent,
        recipient: User,
        preference: MailPreference | None,
    ) -> str | None:
        if not self.sender.authorized(event, recipient):
            return "接收账号不可用或已失去查看原业务记录的权限"
        _, error = self.sender.email_target(
            row, event, recipient, preference, get_settings(), datetime.now(UTC)
        )
        if error is None:
            return None
        return _RECIPIENT_BLOCK_REASONS.get(error, "接收人当前不满足投递条件")

    def list(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        status: MailDeliveryStatus | None,
        kind: MailDeliveryKind | None,
        user_id: int | None,
    ) -> MailDeliveryPage:
        self._require_access(user)
        can_resend = self._can_resend(user)
        rows, total = self.deliveries.list_for_monitor(
            page=page,
            page_size=page_size,
            status=status,
            kind=kind,
            user_id=user_id,
            can_resend=can_resend,
        )
        items = []
        for delivery, recipient, event, preference, generation in rows:
            delivery_status = MailDeliveryStatus(delivery.status)
            block_reason: str | None = _RESEND_PERMISSION_MESSAGE
            if can_resend:
                block_reason = _STATUS_BLOCK_REASONS.get(delivery_status)
                if block_reason is None:
                    block_reason = self._recipient_block_reason(
                        delivery, event, recipient, preference
                    )
            items.append(
                MailDeliveryItem(
                    id=delivery.id,
                    user_id=delivery.user_id,
                    username=recipient.username,
                    display_name=recipient.display_name.strip() or recipient.username,
                    kind=_mail_kind(event.action),
                    status=delivery_status,
                    attempts=delivery.attempts,
                    error_code=_safe_error_code(delivery.last_error),
                    created_at=aware(delivery.created_at).astimezone(UTC),
                    next_attempt_at=_next_attempt_at(delivery),
                    resend_token=(
                        _resend_token(delivery, generation, user.id)
                        if block_reason is None
                        else None
                    ),
                    resend_block_reason=block_reason,
                )
            )
        AuditService(self.db).log(
            "NOTIFICATION",
            None,
            "DELIVERY_MONITOR_VIEW",
            after={
                "page": page,
                "page_size": page_size,
                "status": status,
                "kind": kind,
                "user_id": user_id,
            },
        )
        self.db.commit()
        return MailDeliveryPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            can_resend_mail_deliveries=can_resend,
        )

    def get_detail(self, user: User, delivery_id: str) -> MailDeliveryDetail:
        self._require_access(user)
        row = self.deliveries.get_email_detail(delivery_id)
        if row is None:
            raise NotFoundError("邮件投递记录不存在")
        delivery = row.delivery
        detail = MailDeliveryDetail(
            id=delivery.id,
            username=row.username,
            display_name=row.display_name.strip() or row.username,
            kind=_mail_kind(row.event_action),
            status=MailDeliveryStatus(delivery.status),
            attempts=delivery.attempts,
            error_code=_safe_error_code(delivery.last_error),
            created_at=aware(delivery.created_at).astimezone(UTC),
            next_attempt_at=_next_attempt_at(delivery),
            masked_email=_mask_email(delivery.queued_email),
            event_label=_safe_event_label(row.event_action),
            event_created_at=aware(row.event_created_at).astimezone(UTC),
        )
        AuditService(self.db).log(
            "NOTIFICATION", None, "DELIVERY_DETAIL_VIEW", after={"delivery_id": delivery.id}
        )
        self.db.commit()
        return detail

    def resend(self, user: User, delivery_id: str, token: str) -> None:
        if not self._can_resend(user):
            raise PermissionDenied(_RESEND_PERMISSION_MESSAGE)
        row = self.deliveries.lock_email_delivery(delivery_id)
        if row is None:
            raise NotFoundError("邮件投递记录不存在")
        if row.status not in RESENDABLE_MAIL_STATUSES:
            raise ConflictError(_STATUS_BLOCK_REASONS[MailDeliveryStatus(row.status)])
        generation = self.deliveries.resend_generation(row.id)
        if not hmac.compare_digest(token, _resend_token(row, generation, user.id)):
            raise ConflictError("投递记录已变化。请刷新后重试")

        # Follow the email worker's delivery -> recipient -> preference lock order.
        event = self.db.get(CollaborationEvent, row.event_id)
        recipient = self.db.get(User, row.user_id, with_for_update=True, populate_existing=True)
        if event is None or recipient is None:
            raise ConflictError("原邮件事件或接收账号已不可用")
        preference = self.db.get(
            MailPreference, recipient.id, with_for_update=True, populate_existing=True
        )
        reason = self._recipient_block_reason(row, event, recipient, preference)
        if reason is not None:
            raise ConflictError(reason)

        before = {
            "status": row.status,
            "attempts": row.attempts,
            "error_code": _safe_error_code(row.last_error),
        }
        row.status = "PENDING"
        row.attempts = 0
        row.last_error = None
        row.next_attempt_at = datetime.now(UTC)
        AuditService(self.db).log(
            "NOTIFICATION",
            None,
            "DELIVERY_RESEND",
            before=before,
            after={"delivery_id": row.id, "user_id": row.user_id, "status": row.status},
        )
        self.db.commit()

    def list_recipients(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        keyword: str,
        selected_id: int | None,
    ) -> MailDeliveryRecipientPage:
        self._require_access(user)
        full_directory = self.users.has_enabled_builtin_super_admin_role(user.id) or (
            self.users.data_scope(user.id) is DataScope.ALL
            and not self.users.permission_codes(user.id).isdisjoint({"*", "sys.user.view"})
        )
        rows, total = self.deliveries.list_recipients(
            page=page,
            page_size=page_size,
            keyword=keyword.strip(),
            selected_id=selected_id,
            known_recipients_only=not full_directory,
        )
        items = [
            MailDeliveryRecipient(
                user_id=user_id, display_name=display_name.strip() or username, username=username
            )
            for user_id, display_name, username in rows
        ]
        return MailDeliveryRecipientPage(items=items, page=page, page_size=page_size, total=total)

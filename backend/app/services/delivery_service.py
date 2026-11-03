import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    MailPreference,
    Notification,
    NotificationDelivery,
    Requirement,
    RequirementParticipant,
    User,
    Version,
)
from app.models.enums import NotificationType, UserStatus
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.schemas.mail import DeliveryOut
from app.services.audit_service import AuditService
from app.services.collaboration_service import CollaborationService
from app.services.mail_preferences_service import aware, verification_code

ACTION_LABELS = {
    "RECIPIENT_ADDED": "有反馈需要处理",
    "HANDLER_TRANSFER": "反馈处理人已调整",
    "STATUS_ACCEPTED": "反馈已受理",
    "STATUS_NEW": "反馈重新打开",
    "STATUS_CLOSED": "反馈已关闭",
    "STATUS_DUPLICATE": "反馈已标记重复",
    "STATUS_CANNOT_REPRODUCE": "反馈暂无法复现",
    "STATUS_REQUIREMENT_LINKED": "反馈已关联需求",
    "CREATED": "新需求待确认",
    "REQUEST_CHANGES": "需求需要补充说明",
    "RECONFIRM": "需求内容变更, 待重新确认",
    "CONFIRM": "需求内容已确认",
    "STATUS_CONFIRMED": "需求已确认, 等待开发",
    "STATUS_DEVELOPING": "需求进入开发",
    "STATUS_TESTING": "需求已提交验收",
    "STATUS_DONE": "需求验收通过, 等待发布",
    "STATUS_PAUSED": "需求已暂停",
    "STATUS_CANCELED": "需求已取消",
    "PARTICIPANTS_CHANGE": "环节人员已调整",
    "DESIGN_PENDING": "设计待处理",
    "DESIGN_START": "设计已开始",
    "DESIGN_DONE": "设计已完成",
    "DESIGN_CANCEL": "设计要求已取消",
    "RELATION_CHANGE": "需求版本归属已调整",
    "PUBLISHED": "已随版本上线",
    "VERIFY_EMAIL": "验证通知邮箱",
}


def send_smtp(message: EmailMessage, address: str) -> None:
    settings = get_settings()
    context = ssl.create_default_context()
    connection = (
        smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
        if settings.smtp_security == "ssl"
        else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    )
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(
                settings.smtp_username,
                settings.smtp_password.get_secret_value() if settings.smtp_password else "",
            )
        refused = smtp.send_message(message, from_addr=settings.smtp_from, to_addrs=[address])
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


class DeliveryService:
    def __init__(self, db: Session):
        self.db = db

    def authorized(self, event: CollaborationEvent, user: User) -> bool:
        if user.status != UserStatus.ACTIVE:
            return False
        if event.entity_type == "ACCOUNT":
            return event.entity_id == user.id
        repo = UserRepository(self.db)
        kind = event.entity_type.lower()
        if f"rd.{kind}.view" not in repo.permission_codes(
            user.id
        ) and "*" not in repo.permission_codes(user.id):
            return False
        scope = repo.data_scope(user.id)
        if kind == "feedback":
            feedback = FeedbackRepository(self.db).get_scoped(event.entity_id, user.id, scope)
            if not feedback:
                return False
            return user.id in {
                feedback.submitter_id,
                feedback.handler_id,
                *CollaborationService(self.db).recipient_ids(feedback.id),
            }
        if kind == "requirement":
            req = RequirementRepository(self.db).get_scoped(event.entity_id, user.id, scope)
            if not req:
                return False
            participants = set(
                self.db.scalars(
                    select(RequirementParticipant.user_id).where(
                        RequirementParticipant.requirement_id == req.id,
                        RequirementParticipant.active.is_(True),
                    )
                )
            )
            if user.id in {req.created_by, req.owner_id, *participants}:
                return True
            version = (
                self.db.get(Version, req.current_version_id) if req.current_version_id else None
            )
            return bool(
                version
                and version.owner_id == user.id
                and event.action in {"RELATION_CHANGE", "STATUS_DONE", "PUBLISHED"}
            )
        return False

    def is_task(self, event: CollaborationEvent, uid: int) -> bool:
        if event.action in {
            "PUBLISHED",
            "RECIPIENT_ADDED",
            "HANDLER_TRANSFER",
            "PARTICIPANTS_CHANGE",
        }:
            return True
        if event.entity_type == "REQUIREMENT" and event.action == "STATUS_DONE":
            item = self.db.get(Requirement, event.entity_id)
            version = (
                self.db.get(Version, item.current_version_id)
                if item and item.current_version_id
                else None
            )
            return bool(version and version.owner_id == uid)
        if event.action == "REQUEST_CHANGES":
            item = self.db.get(Requirement, event.entity_id)
            return bool(item and item.created_by == uid)
        required_role = {
            "CREATED": "CONFIRM",
            "RECONFIRM": "CONFIRM",
            "CONFIRM": "DEVELOP",
            "STATUS_CONFIRMED": "DEVELOP",
            "STATUS_TESTING": "ACCEPT",
            "STATUS_DEVELOPING": "DEVELOP",
            "DESIGN_PENDING": "DESIGN",
        }.get(event.action)
        if event.entity_type == "REQUIREMENT" and required_role:
            person = self.db.get(RequirementParticipant, (event.entity_id, uid, required_role))
            return bool(person and person.active)
        return False

    def expand(self, limit: int = 100) -> int:
        events = list(
            self.db.scalars(
                select(CollaborationEvent)
                .where(CollaborationEvent.processed_at.is_(None))
                .order_by(CollaborationEvent.created_at, CollaborationEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=self.db.get_bind().dialect.name != "mysql")
            )
        )
        for event in events:
            for uid in sorted(set(event.recipient_ids)):
                user = self.db.get(User, uid)
                if not user:
                    continue
                pref = self.db.get(MailPreference, uid)
                email = (
                    pref.pending_email if event.action == "VERIFY_EMAIL" and pref else user.email
                )
                channels = ["EMAIL"] if event.action == "VERIFY_EMAIL" else ["SITE", "EMAIL"]
                for channel in channels:
                    self.db.add(
                        NotificationDelivery(
                            event_id=event.id, user_id=uid, channel=channel, queued_email=email
                        )
                    )
            event.processed_at = datetime.now(UTC)
        self.db.commit()
        return len(events)

    def _message(self, event: CollaborationEvent, delivery: NotificationDelivery, email: str):
        settings = get_settings()
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = email
        message["Message-ID"] = f"<{delivery.id}@iterflow.notifications>"
        if event.action == "VERIFY_EMAIL":
            message["Subject"] = "迭程 IterFlow · 邮箱验证"
            message.set_content(
                f"验证码: {verification_code(event.id)}\n15 分钟内有效。"
                "请在已登录的个人中心输入;这不会确认任何业务流程。"
            )
        else:
            title, content = self._text(event)
            message["Subject"] = f"迭程 IterFlow · {title}"
            path = "feedbacks" if event.entity_type == "FEEDBACK" else "requirements"
            message.set_content(
                f"{content}\n{settings.app_public_url.rstrip('/')}/#/{path}/{event.entity_id}\n通知送达不表示业务已确认。"
            )
        return message

    @staticmethod
    def _text(event: CollaborationEvent):
        action = event.action.removeprefix("REQUIREMENT_")
        label = ACTION_LABELS.get(action, "协作进度已更新")
        kind = "反馈" if event.entity_type == "FEEDBACK" else "需求"
        if event.action.startswith("REQUIREMENT_"):
            label = "关联需求进度更新: " + label
        title = f"{kind} #{event.entity_id} · {label}"
        return title, title + "。请登录查看当前进度。"

    def deliver_one(self) -> bool:
        now = datetime.now(UTC)
        row = self.db.scalar(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status.in_(["PENDING", "RETRY", "UNCERTAIN", "SENDING"]),
                NotificationDelivery.next_attempt_at <= now,
            )
            .order_by(NotificationDelivery.next_attempt_at, NotificationDelivery.id)
            .limit(1)
            .with_for_update(skip_locked=self.db.get_bind().dialect.name != "mysql")
        )
        if row is None:
            self.db.rollback()
            return False
        if row.attempts >= 5:
            row.status = "FAILED"
            row.last_error = "RETRY_LIMIT"
            self.db.commit()
            return True
        row.status = "SENDING"
        row.attempts += 1
        row.next_attempt_at = now + timedelta(minutes=5)
        row_id = row.id
        self.db.commit()  # Durable lease survives a worker crash before or after SMTP.
        row = self.db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.id == row_id).with_for_update()
        )
        assert row is not None
        self.db.expire_all()
        event = self.db.get(CollaborationEvent, row.event_id)
        user = self.db.get(
            User,
            row.user_id,
            with_for_update=row.channel == "EMAIL",
            populate_existing=True,
        )
        if not event or not user or not self.authorized(event, user):
            row.status = "SKIPPED"
            row.last_error = "ACCESS_REVOKED"
            self.db.commit()
            return True
        if row.channel == "SITE":
            # Publish already creates the submitter's site notification atomically.
            feedback = (
                self.db.get(Feedback, event.entity_id) if event.entity_type == "FEEDBACK" else None
            )
            existing_publish = (
                event.action == "PUBLISHED"
                and event.entity_type == "FEEDBACK"
                and feedback is not None
                and feedback.submitter_id == user.id
            )
            if not existing_publish:
                title, content = self._text(event)
                self.db.add(
                    Notification(
                        user_id=user.id,
                        type=NotificationType.FEEDBACK
                        if event.entity_type == "FEEDBACK"
                        else NotificationType.REQUIREMENT,
                        title=title,
                        content=content,
                        entity_type=event.entity_type,
                        entity_id=event.entity_id,
                    )
                )
            row.status = "SENT"
            self.db.commit()
            return True
        settings = get_settings()
        # Match email changes/unbinding's user -> preference lock order. Keep the
        # account locked until SMTP finishes so a completed unbind cannot be raced.
        pref = self.db.get(MailPreference, user.id, with_for_update=True, populate_existing=True)
        email = user.email
        eligible = bool(
            pref
            and pref.mode != "OFF"
            and pref.verified_email
            and pref.verified_email == user.email
            and pref.verified_at is not None
            and aware(event.created_at) >= aware(pref.verified_at)
            and (pref.mode == "ALL" or self.is_task(event, user.id))
        )
        if event.action == "VERIFY_EMAIL":
            email = pref.pending_email if pref else None
            eligible = bool(
                pref
                and pref.challenge_id == event.id
                and pref.challenge_expires_at
                and aware(pref.challenge_expires_at) > now
                and pref.challenge_user_revision == user.revision
            )
        if not eligible or not email or email != row.queued_email:
            row.status = "SKIPPED"
            row.last_error = "PREFERENCE_OR_EMAIL_CHANGED"
            self.db.commit()
            return True
        if not settings.smtp_enabled:
            row.status = "RETRY"
            row.last_error = "SMTP_DISABLED"
            row.attempts -= 1
            row.next_attempt_at = now + timedelta(minutes=5)
            self.db.commit()
            return True
        if settings.app_env != "production" and email.lower() not in {
            x.strip().lower() for x in settings.smtp_allowlist.split(",")
        }:
            row.status = "SKIPPED"
            row.last_error = "NOT_ALLOWLISTED"
            self.db.commit()
            return True
        try:
            send_smtp(self._message(event, row, email), email)
            row.status = "SENT"
            row.last_error = None
        except (TimeoutError, smtplib.SMTPServerDisconnected):
            row.status = "UNCERTAIN"
            row.last_error = "SMTP_OUTCOME_UNCERTAIN"
        except smtplib.SMTPRecipientsRefused:
            row.status = "FAILED"
            row.last_error = "SMTP_RECIPIENT_REFUSED"
        except smtplib.SMTPResponseException as exc:
            row.status = "FAILED" if exc.smtp_code >= 500 else "RETRY"
            row.last_error = f"SMTP_{exc.smtp_code}"
        except (OSError, smtplib.SMTPException):
            row.status = "RETRY"
            row.last_error = "SMTP_CONNECTION_ERROR"
        if row.status in {"RETRY", "UNCERTAIN"}:
            row.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2**row.attempts))
            if row.attempts >= 5:
                row.status = "FAILED"
        self.db.commit()
        return True

    def list_deliveries(self, page: int, status: str | None):
        query = select(NotificationDelivery).where(NotificationDelivery.channel == "EMAIL")
        if status:
            query = query.where(NotificationDelivery.status == status)
        rows = list(
            self.db.scalars(
                query.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id)
                .offset((page - 1) * 50)
                .limit(50)
            )
        )
        AuditService(self.db).log(
            "NOTIFICATION", None, "DELIVERY_VIEW", after={"page": page, "status": status}
        )
        self.db.commit()
        return rows

    def retry(self, delivery_id: str, attempts: int):
        row = self.db.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .with_for_update()
        )
        if row is None:
            raise NotFoundError("投递记录不存在")
        if row.status != "FAILED" or row.attempts != attempts:
            raise ConflictError("仅可重试当前失败记录")
        row.status = "PENDING"
        row.attempts = 0
        row.next_attempt_at = datetime.now(UTC)
        AuditService(self.db).log(
            "NOTIFICATION", None, "DELIVERY_RETRY", after={"delivery_id": row.id}
        )
        self.db.commit()
        return DeliveryOut.model_validate(row)

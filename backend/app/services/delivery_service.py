# ruff: noqa: RUF001
import smtplib
import ssl
from datetime import UTC, datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from urllib.parse import urlsplit

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
from app.services.mail_preferences_service import (
    aware,
    current_email_challenge_id,
    current_email_verified_at,
    verification_code,
)

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
    "RECONFIRM": "需求内容变更，待重新确认",
    "CONFIRM": "需求内容已确认",
    "REOPEN": "需求已重新打开，待确认",
    "STATUS_CONFIRMED": "需求已确认，等待开发",
    "STATUS_DEVELOPING": "需求进入开发",
    "STATUS_TESTING": "需求已提交验收",
    "STATUS_DONE": "需求验收通过，等待发布",
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

MAIL_TIMEZONE = timezone(timedelta(hours=8), name="UTC+08:00")


def _mail_time(value: datetime) -> str:
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    return value.astimezone(MAIL_TIMEZONE).strftime("%Y年%m月%d日 %H:%M")


def _safe_subject(value: str) -> str:
    return " ".join(value.split())[:80]


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
            "REOPEN": "CONFIRM",
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
            code = verification_code(event.id)
            public_url = urlsplit(settings.app_public_url)
            profile_url = public_url._replace(
                path=f"{public_url.path.rstrip('/')}/",
                query="",
                fragment="/profile#mail-notifications",
            ).geturl()
            intro = "请完成迭程 IterFlow 账号的通知邮箱验证。"
            instructions = "验证码 15 分钟内有效。请登录后在个人中心的「邮件通知」输入验证码。"
            ignore = "如果您不认识此账号，可忽略此邮件。"
            message["Subject"] = "迭程 IterFlow｜验证通知邮箱"
            message.set_content(
                f"您好，\n\n{intro}\n"
                f"验证码：{code}\n\n{instructions}\n"
                f"打开个人中心：\n{profile_url}\n\n"
                f"{ignore}\n\n迭程 IterFlow"
            )
            message.add_alternative(
                self._html_message(
                    eyebrow="账号安全",
                    heading="验证您的通知邮箱",
                    intro=intro,
                    details=(
                        '<div style="margin:24px 0;padding:18px 20px;background:#f4f5f7;'
                        "border-radius:6px;text-align:center;font-size:30px;font-weight:700;"
                        f'letter-spacing:6px;color:#202124">{escape(code)}</div>'
                    ),
                    button_label="打开个人中心",
                    button_url=profile_url,
                    note=f"{escape(instructions)}<br>{escape(ignore)}",
                ),
                subtype="html",
            )
        else:
            feedback = None
            record: Feedback | Requirement | None
            if event.entity_type == "FEEDBACK":
                feedback = self.db.get(Feedback, event.entity_id)
                record = feedback
            else:
                record = self.db.get(Requirement, event.entity_id)
            record_title = record.title if record else f"{event.entity_type} #{event.entity_id}"
            kind = "反馈" if event.entity_type == "FEEDBACK" else "需求"
            action = event.action.removeprefix("REQUIREMENT_")
            label = ACTION_LABELS.get(action, "协作进度有更新")
            if event.action.startswith("REQUIREMENT_"):
                label = "关联需求有新进展：" + label
            event_time = _mail_time(event.created_at)
            if (
                event.action == "STATUS_ACCEPTED"
                and feedback
                and feedback.submitter_id == delivery.user_id
            ):
                summary = (
                    f"您于 {_mail_time(feedback.created_at)} 提交的反馈《{record_title}》已受理。"
                )
                heading = "您提交的反馈已受理"
            else:
                summary = f"{kind}《{record_title}》于 {event_time} 更新：{label}。"
                heading = f"{kind}有新进展"
            path = "feedbacks" if event.entity_type == "FEEDBACK" else "requirements"
            link = f"{settings.app_public_url.rstrip('/')}/#/{path}/{event.entity_id}"
            link_label = f"查看{kind}详情"
            message["Subject"] = (
                f"迭程 IterFlow｜{_safe_subject(label)}：{_safe_subject(record_title)}"
            )
            message.set_content(
                f"您好，\n\n{summary}\n\n{link_label}：\n{link}\n\n"
                f"{kind}编号：#{event.entity_id}\n\n"
                "此邮件由迭程 IterFlow 自动发送。业务状态以系统记录为准。"
            )
            message.add_alternative(
                self._html_message(
                    eyebrow=f"{kind}进度通知",
                    heading=heading,
                    intro=summary,
                    details=(
                        f'<div style="margin:22px 0 6px;padding:14px 16px;'
                        f'background:#f4f5f7;border-radius:6px;color:#5f6368;font-size:14px">'
                        f"{escape(kind)}编号：#{event.entity_id}<br>"
                        f"更新时间：{escape(event_time)}</div>"
                    ),
                    button_label=link_label,
                    button_url=link,
                    note="此邮件由迭程 IterFlow 自动发送。业务状态以系统记录为准。",
                ),
                subtype="html",
            )
        return message

    @staticmethod
    def _html_message(
        *,
        eyebrow: str,
        heading: str,
        intro: str,
        details: str = "",
        button_label: str | None = None,
        button_url: str | None = None,
        note: str,
    ) -> str:
        button = ""
        if button_label and button_url:
            safe_url = escape(button_url, quote=True)
            button = (
                '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
                'style="margin:26px 0 12px"><tr><td bgcolor="#202124" '
                'style="border-radius:5px"><a href="'
                f'{safe_url}" style="display:inline-block;padding:13px 22px;color:#ffffff;'
                f'text-decoration:none;font-size:15px;font-weight:600">'
                f"{escape(button_label)}</a></td></tr></table>"
                f'<p style="margin:12px 0 0;font-size:12px;line-height:1.6;color:#74777c">'
                f"如果按钮无法打开，请复制此链接到浏览器：<br>"
                f'<a href="{safe_url}" style="color:#345f9f;word-break:break-all">'
                f"{escape(button_url)}</a></p>"
            )
        return (
            '<!doctype html><html><body style="margin:0;padding:24px 12px;'
            "background:#f3f4f5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,"
            'sans-serif;color:#202124"><table role="presentation" width="100%" '
            'cellspacing="0" cellpadding="0" border="0"><tr><td align="center">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'border="0" style="max-width:620px;background:#ffffff"><tr><td '
            'style="padding:26px 32px 20px;border-bottom:1px solid #e8e9eb">'
            '<div style="font-size:20px;line-height:1.3;font-weight:700;color:#202124">'
            '迭程 <span style="font-weight:500;color:#5f6368">IterFlow</span></div>'
            '</td></tr><tr><td style="padding:32px">'
            f'<div style="margin-bottom:12px;font-size:12px;line-height:1.4;'
            f'font-weight:600;color:#68717c">{escape(eyebrow)}</div>'
            f'<h1 style="margin:0 0 18px;font-size:25px;line-height:1.4;'
            f'font-weight:650;color:#202124">{escape(heading)}</h1>'
            f'<p style="margin:0;font-size:15px;line-height:1.8;color:#3c4043">'
            f"{escape(intro)}</p>{details}{button}"
            f'<p style="margin:28px 0 0;padding-top:18px;border-top:1px solid #e8e9eb;'
            f'font-size:12px;line-height:1.7;color:#74777c">{note}</p>'
            '</td></tr><tr><td style="padding:16px 32px 24px;font-size:12px;'
            'color:#8a8d91">迭程 IterFlow · 需求与版本协作管理系统</td></tr>'
            "</table></td></tr></table></body></html>"
        )

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
        verified_at = current_email_verified_at(email, pref)
        eligible = bool(
            pref
            and pref.mode != "OFF"
            and verified_at is not None
            and aware(event.created_at) >= aware(verified_at)
            and (pref.mode == "ALL" or self.is_task(event, user.id))
        )
        if event.action == "VERIFY_EMAIL":
            email = pref.pending_email if pref else None
            eligible = current_email_challenge_id(pref, user.revision, now) == event.id
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

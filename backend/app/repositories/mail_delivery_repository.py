from datetime import datetime
from typing import NamedTuple

from sqlalchemy import ColumnElement, case, func, literal, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session, load_only

from app.models.entities import (
    CollaborationEvent,
    MailPreference,
    NotificationDelivery,
    OperationLog,
    User,
)

RESENDABLE_MAIL_STATUSES = ("SENT", "FAILED")


class MailDeliveryMonitorRow(NamedTuple):
    delivery: NotificationDelivery
    recipient: User
    event: CollaborationEvent
    preference: MailPreference | None
    resend_generation: int | None


class MailDeliveryDetailRow(NamedTuple):
    delivery: NotificationDelivery
    username: str
    display_name: str
    event_action: str
    event_created_at: datetime


def _resend_history(
    delivery_id: str | InstrumentedAttribute[str],
    actions: tuple[str, ...] = ("DELIVERY_RETRY", "DELIVERY_RESEND"),
):
    # A delivery may return to the same terminal status and attempt count. The
    # committed audit sequence distinguishes its successive manual queue cycles.
    return select(func.max(OperationLog.id)).where(
        OperationLog.entity_type == "NOTIFICATION",
        OperationLog.action.in_(actions),
        OperationLog.after_data["delivery_id"].as_string() == delivery_id,
    )


class MailDeliveryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_monitor(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None,
        kind: str | None,
        user_id: int | None,
        can_resend: bool,
    ) -> tuple[list[MailDeliveryMonitorRow], int]:
        delivery = NotificationDelivery
        filters = [delivery.channel == "EMAIL"]
        if status is not None:
            filters.append(delivery.status == status)
        if kind == "EMAIL_VERIFICATION":
            filters.append(CollaborationEvent.action == "VERIFY_EMAIL")
        elif kind == "COLLABORATION":
            filters.append(CollaborationEvent.action != "VERIFY_EMAIL")
        if user_id is not None:
            filters.append(delivery.user_id == user_id)

        total = (
            self.db.scalar(
                select(func.count())
                .select_from(delivery)
                .join(CollaborationEvent, CollaborationEvent.id == delivery.event_id)
                .where(*filters)
            )
            or 0
        )
        offset = (page - 1) * page_size
        if offset >= total:
            return [], total

        generation: ColumnElement[int | None] = (
            case(
                (
                    delivery.status.in_(RESENDABLE_MAIL_STATUSES),
                    _resend_history(delivery.id).correlate(delivery).scalar_subquery(),
                )
            )
            if can_resend
            else literal(None)
        )
        rows = self.db.execute(
            select(delivery, User, CollaborationEvent, MailPreference, generation)
            .join(User, User.id == delivery.user_id)
            .join(CollaborationEvent, CollaborationEvent.id == delivery.event_id)
            .outerjoin(MailPreference, MailPreference.user_id == User.id)
            .options(
                load_only(
                    delivery.id,
                    delivery.user_id,
                    delivery.status,
                    delivery.attempts,
                    delivery.last_error,
                    delivery.created_at,
                    delivery.next_attempt_at,
                    delivery.queued_email,
                    raiseload=True,
                ),
                load_only(
                    User.username,
                    User.display_name,
                    User.email,
                    User.status,
                    User.revision,
                    raiseload=True,
                ),
                load_only(
                    CollaborationEvent.action,
                    CollaborationEvent.entity_type,
                    CollaborationEvent.entity_id,
                    CollaborationEvent.created_at,
                    raiseload=True,
                ),
                load_only(
                    MailPreference.mode,
                    MailPreference.verified_email,
                    MailPreference.verified_at,
                    MailPreference.pending_email,
                    MailPreference.challenge_id,
                    MailPreference.challenge_expires_at,
                    MailPreference.challenge_attempts,
                    MailPreference.challenge_user_revision,
                    raiseload=True,
                ),
            )
            .where(*filters)
            .order_by(delivery.created_at.desc(), delivery.id)
            .offset(offset)
            .limit(page_size)
        )
        return [MailDeliveryMonitorRow(*row) for row in rows], total

    def get_email_detail(self, delivery_id: str) -> MailDeliveryDetailRow | None:
        delivery = NotificationDelivery
        row = self.db.execute(
            select(
                delivery,
                User.username,
                User.display_name,
                CollaborationEvent.action,
                CollaborationEvent.created_at,
            )
            .join(User, User.id == delivery.user_id)
            .join(CollaborationEvent, CollaborationEvent.id == delivery.event_id)
            .options(
                load_only(
                    delivery.id,
                    delivery.status,
                    delivery.attempts,
                    delivery.last_error,
                    delivery.created_at,
                    delivery.next_attempt_at,
                    delivery.queued_email,
                    raiseload=True,
                )
            )
            .where(delivery.id == delivery_id, delivery.channel == "EMAIL")
        ).one_or_none()
        return MailDeliveryDetailRow(*row) if row is not None else None

    def lock_email_delivery(self, delivery_id: str) -> NotificationDelivery | None:
        delivery = NotificationDelivery
        return self.db.scalar(
            select(delivery)
            .where(delivery.id == delivery_id, delivery.channel == "EMAIL")
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def resend_generation(self, delivery_id: str) -> int | None:
        return self.db.scalar(_resend_history(delivery_id))

    def message_generation(self, delivery_id: str) -> int | None:
        # Keep the Message-ID of a legacy retry that was already queued before
        # this endpoint was introduced.
        return self.db.scalar(_resend_history(delivery_id, ("DELIVERY_RESEND",)))

    def list_recipients(
        self,
        *,
        page: int,
        page_size: int,
        keyword: str,
        selected_id: int | None,
        known_recipients_only: bool,
    ) -> tuple[list[tuple[int, str, str]], int]:
        filters: list[ColumnElement[bool]] = []
        if known_recipients_only:
            filters.append(
                select(NotificationDelivery.id)
                .where(
                    NotificationDelivery.user_id == User.id,
                    NotificationDelivery.channel == "EMAIL",
                )
                .exists()
            )
        if selected_id is not None:
            filters.append(User.id == selected_id)
        if keyword:
            escaped_keyword = keyword.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            pattern = f"%{escaped_keyword}%"
            filters.append(
                or_(
                    User.display_name.ilike(pattern, escape="!"),
                    User.username.ilike(pattern, escape="!"),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
        offset = (page - 1) * page_size
        if offset >= total:
            return [], total
        rows = self.db.execute(
            select(User.id, User.display_name, User.username)
            .where(*filters)
            .order_by(User.display_name, User.username, User.id)
            .offset(offset)
            .limit(page_size)
        )
        return [
            (user_id, display_name, username) for user_id, display_name, username in rows
        ], total

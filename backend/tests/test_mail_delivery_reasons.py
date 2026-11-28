from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import CollaborationEvent, MailPreference, NotificationDelivery, User
from app.services.delivery_service import DeliveryService
from app.services.mail_delivery_monitor_service import _safe_error_code

ADDRESS = "recipient@example.test"
OLDER_ADDRESS = "old@example.test"
NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("email", "queued_email", "verified_email", "verified_at", "mode", "action", "error"),
    [
        (None, ADDRESS, None, None, "ALL", "STATUS_ACCEPTED", "EMAIL_NOT_CONFIGURED"),
        (
            ADDRESS,
            OLDER_ADDRESS,
            OLDER_ADDRESS,
            NOW,
            "ALL",
            "STATUS_ACCEPTED",
            "EMAIL_ADDRESS_CHANGED",
        ),
        (ADDRESS, ADDRESS, OLDER_ADDRESS, NOW, "ALL", "STATUS_ACCEPTED", "EMAIL_NOT_VERIFIED"),
        (
            ADDRESS,
            ADDRESS,
            ADDRESS,
            NOW + timedelta(seconds=1),
            "ALL",
            "STATUS_ACCEPTED",
            "EVENT_BEFORE_EMAIL_VERIFICATION",
        ),
        (ADDRESS, ADDRESS, ADDRESS, NOW, "OFF", "STATUS_ACCEPTED", "EMAIL_NOTIFICATIONS_OFF"),
        (ADDRESS, ADDRESS, ADDRESS, NOW, "TASKS", "STATUS_ACCEPTED", "EMAIL_NOT_A_TASK"),
        (ADDRESS, ADDRESS, ADDRESS, NOW, "TASKS", "RECIPIENT_ADDED", None),
    ],
)
def test_collaboration_delivery_reasons(
    email, queued_email, verified_email, verified_at, mode, action, error
):
    user = User(id=1, email=email, revision=1)
    preference = MailPreference(mode=mode, verified_email=verified_email, verified_at=verified_at)
    event = CollaborationEvent(action=action, entity_type="FEEDBACK", created_at=NOW)
    row = NotificationDelivery(queued_email=queued_email)
    settings = get_settings().model_copy(update={"smtp_enabled": True, "app_env": "production"})

    with Session() as db:
        assert DeliveryService(db).email_target(row, event, user, preference, settings, NOW) == (
            None if error else email,
            error,
        )
    assert _safe_error_code(error) == error


@pytest.mark.parametrize(
    ("challenge_overrides", "queued_email", "settings_overrides", "error"),
    [
        ({"challenge_expires_at": NOW}, ADDRESS, {}, "VERIFICATION_EXPIRED_OR_REPLACED"),
        ({"challenge_id": "replacement"}, ADDRESS, {}, "VERIFICATION_EXPIRED_OR_REPLACED"),
        ({"pending_email": None}, ADDRESS, {}, "VERIFICATION_EXPIRED_OR_REPLACED"),
        ({"challenge_user_revision": 2}, ADDRESS, {}, "VERIFICATION_EXPIRED_OR_REPLACED"),
        ({"challenge_attempts": 5}, ADDRESS, {}, "VERIFICATION_EXPIRED_OR_REPLACED"),
        ({}, OLDER_ADDRESS, {}, "EMAIL_ADDRESS_CHANGED"),
        ({}, ADDRESS, {"smtp_enabled": False}, "SMTP_DISABLED"),
        ({}, ADDRESS, {"app_env": "test", "smtp_allowlist": ""}, "NOT_ALLOWLISTED"),
        ({}, ADDRESS, {"app_env": "test", "smtp_allowlist": f" {ADDRESS.upper()} "}, None),
    ],
)
def test_verification_delivery_reasons(
    challenge_overrides, queued_email, settings_overrides, error
):
    user = User(id=1, email=None, revision=1)
    event = CollaborationEvent(id="challenge", action="VERIFY_EMAIL", created_at=NOW)
    preference = MailPreference(
        **{
            "mode": "OFF",
            "pending_email": ADDRESS,
            "challenge_id": event.id,
            "challenge_user_revision": user.revision,
            "challenge_expires_at": NOW + timedelta(minutes=15),
            "challenge_attempts": 0,
            **challenge_overrides,
        }
    )
    row = NotificationDelivery(queued_email=queued_email)
    settings = get_settings().model_copy(
        update={"smtp_enabled": True, "app_env": "production", **settings_overrides}
    )

    with Session() as db:
        assert DeliveryService(db).email_target(row, event, user, preference, settings, NOW) == (
            None if error else ADDRESS,
            error,
        )
    assert _safe_error_code(error) == error


def test_monitor_keeps_the_historical_reason_and_masks_unrecognized_values():
    assert _safe_error_code("PREFERENCE_OR_EMAIL_CHANGED") == "PREFERENCE_OR_EMAIL_CHANGED"
    assert _safe_error_code("SMTP_550") == "SMTP_550"
    assert _safe_error_code(f"SMTP_550 rejected {ADDRESS}") == "UNKNOWN"

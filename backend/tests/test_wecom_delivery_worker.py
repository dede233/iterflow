from datetime import UTC, datetime, timedelta
from itertools import count
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.wecom import WecomDeliveryError
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    FeedbackRecipient,
    MailPreference,
    Notification,
    NotificationDelivery,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    WecomPreference,
)
from app.models.enums import DataScope, FeedbackType, UserStatus
from app.services.delivery_service import DeliveryService


@pytest.fixture
def worker(monkeypatch):
    settings = get_settings().model_copy(
        update={
            "app_env": "test",
            "app_public_url": "https://iterflow.example.test/app",
            "wecom_enabled": True,
            "wecom_corp_id": "corp-original",
            "wecom_allowlist": "Member_2",
            "smtp_enabled": True,
            "smtp_allowlist": "mail@example.test",
        }
    )
    monkeypatch.setattr("app.services.delivery_service.get_settings", lambda: settings)
    sender = Mock()
    smtp = Mock()
    monkeypatch.setattr("app.services.delivery_service.send_wecom", sender)
    monkeypatch.setattr("app.services.delivery_service.send_smtp", smtp)
    engine = create_engine("sqlite://")
    for model in (
        User,
        Role,
        Permission,
        UserRole,
        RolePermission,
        Feedback,
        FeedbackRecipient,
        CollaborationEvent,
        MailPreference,
        WecomPreference,
        NotificationDelivery,
        OperationLog,
        Notification,
    ):
        model.__table__.create(engine)
    notification_ids = count(1)

    def assign_id(_mapper, _connection, notification):
        notification.id = next(notification_ids)

    event.listen(Notification, "before_insert", assign_id)
    try:
        with Session(engine, expire_on_commit=False) as db:
            eligible_at = datetime.now(UTC) - timedelta(minutes=1)
            db.add_all(
                [
                    User(
                        id=1, username="submitter", display_name="Submitter", password_hash="unused"
                    ),
                    User(
                        id=2,
                        username="member",
                        display_name="Member",
                        password_hash="unused",
                        email="mail@example.test",
                    ),
                    Role(
                        id=1, code="FEEDBACK_DESK", name="Feedback desk", data_scope=DataScope.ALL
                    ),
                    Permission(id=1, code="rd.feedback.view", name="View feedback"),
                    UserRole(user_id=2, role_id=1),
                    RolePermission(role_id=1, permission_id=1),
                    Feedback(
                        id=41,
                        feedback_no="F-41",
                        title="Private object title",
                        description="Private object content",
                        submitter_id=1,
                        feedback_type=FeedbackType.OTHER,
                    ),
                    FeedbackRecipient(feedback_id=41, user_id=2),
                    MailPreference(
                        user_id=2,
                        mode="ALL",
                        verified_email="mail@example.test",
                        verified_at=eligible_at,
                    ),
                    WecomPreference(
                        user_id=2,
                        mode="TASKS",
                        corp_id=settings.wecom_corp_id,
                        member_user_id="Member_2",
                        member_key="member_2",
                        binding_id=str(uuid4()),
                        eligible_since=eligible_at,
                    ),
                ]
            )
            db.commit()
            yield db, DeliveryService(db), settings, sender, smtp
    finally:
        event.remove(Notification, "before_insert", assign_id)
        engine.dispose()


def queue_event(db, *, action="RECIPIENT_ADDED", entity_type="FEEDBACK", created_at=None):
    item = CollaborationEvent(
        action=action,
        entity_type=entity_type,
        entity_id=2 if entity_type == "ACCOUNT" else 41,
        actor_id=1,
        recipient_ids=[2, 2],
        created_at=created_at or datetime.now(UTC),
    )
    db.add(item)
    db.commit()
    return item


def deliveries(db, event_id):
    return {
        row.channel: row
        for row in db.scalars(
            select(NotificationDelivery).where(NotificationDelivery.event_id == event_id)
        )
    }


def drain(service):
    for _ in range(30):
        if not service.deliver_one():
            return
    pytest.fail("notification worker did not drain")


def test_worker_wecom_design_targets_one_consented_recipient_without_changing_other_channels(
    worker,
):
    db, service, settings, sender, smtp = worker
    old_event = queue_event(db, created_at=datetime.now(UTC) - timedelta(minutes=2))
    status_change = queue_event(db, action="STATUS_CLOSED")
    verification = queue_event(db, action="VERIFY_EMAIL", entity_type="ACCOUNT")
    task = queue_event(db)
    other_task = queue_event(db)
    assert service.expand() == 5
    assert service.expand() == 0
    assert set(deliveries(db, old_event.id)) == {"EMAIL", "SITE"}
    assert set(deliveries(db, status_change.id)) == {"EMAIL", "SITE"}
    assert set(deliveries(db, verification.id)) == {"EMAIL"}
    channels = deliveries(db, task.id)
    assert set(channels) == {"EMAIL", "SITE", "WECOM"}
    assert channels["WECOM"].queued_email is None
    assert channels["WECOM"].queued_wecom_binding_id == db.get(WecomPreference, 2).binding_id
    assert not sender.called and not smtp.called

    drain(service)
    drain(service)
    assert sender.call_count == 2
    urls = set()
    for call in sender.call_args_list:
        config, member, description, url = call.args
        assert config is settings
        assert member == "Member_2"
        assert "#41" in description and "Private" not in description
        assert url.startswith("https://iterflow.example.test/app/#/feedbacks/41?notification=")
        urls.add(url)
    assert {url.rsplit("=", 1)[1] for url in urls} == {
        deliveries(db, item.id)["WECOM"].id for item in (task, other_task)
    }
    assert smtp.call_count == 3
    assert all(call.args[1] == "mail@example.test" for call in smtp.call_args_list)
    assert len(list(db.scalars(select(Notification)))) == 4
    assert all(row.status == "SENT" for row in channels.values())


def test_worker_all_mode_and_disabled_defaults(worker):
    db, service, settings, sender, _smtp = worker
    settings.wecom_enabled = False
    disabled = queue_event(db)
    service.expand()
    settings.wecom_enabled = True
    db.get(WecomPreference, 2).mode = "ALL"
    all_update = queue_event(db, action="STATUS_CLOSED")
    service.expand()
    drain(service)
    assert set(deliveries(db, disabled.id)) == {"EMAIL", "SITE"}
    assert deliveries(db, all_update.id)["WECOM"].status == "SENT"
    assert sender.call_count == 1


def test_worker_revalidates_corporation_before_using_a_member_id(worker):
    db, service, settings, sender, _smtp = worker
    queued = queue_event(db)
    service.expand()
    settings.wecom_corp_id = "corp-replacement"
    stale_binding = queue_event(db)
    service.expand()
    drain(service)
    prior_delivery = deliveries(db, queued.id)["WECOM"]
    assert prior_delivery.status == "SKIPPED"
    assert prior_delivery.last_error == "WECOM_PREFERENCE_OR_BINDING_CHANGED"
    assert "WECOM" not in deliveries(db, stale_binding.id)
    assert not sender.called

    pref = db.get(WecomPreference, 2)
    pref.corp_id = settings.wecom_corp_id
    pref.binding_id = str(uuid4())
    pref.eligible_since = datetime.now(UTC)
    after_rebind = queue_event(db)
    service.expand()
    drain(service)
    assert deliveries(db, after_rebind.id)["WECOM"].status == "SENT"
    assert sender.call_args.args[1] == "Member_2"
    assert sender.call_count == 1


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        ("off", "WECOM_PREFERENCE_OR_BINDING_CHANGED"),
        ("rebind", "WECOM_PREFERENCE_OR_BINDING_CHANGED"),
        ("mode-change", "WECOM_PREFERENCE_OR_BINDING_CHANGED"),
        ("role", "ACCESS_REVOKED"),
        ("scope", "ACCESS_REVOKED"),
        ("receiver", "ACCESS_REVOKED"),
        ("inactive", "ACCESS_REVOKED"),
        ("allowlist", "WECOM_NOT_ALLOWLISTED"),
        ("production-allowlist", "WECOM_NOT_ALLOWLISTED"),
        ("disabled", "WECOM_DISABLED"),
    ],
)
def test_worker_rechecks_binding_and_access_at_delivery(worker, change, expected_error):
    db, service, settings, sender, _smtp = worker
    task = queue_event(db)
    service.expand()
    assert deliveries(db, task.id)["WECOM"].status == "PENDING"
    pref = db.get(WecomPreference, 2)
    if change == "off":
        pref.mode = "OFF"
    elif change == "rebind":
        pref.binding_id = str(uuid4())  # Same member ID can have a new binding generation.
    elif change == "mode-change":
        pref.mode = "ALL"
        pref.eligible_since = datetime.now(UTC)
    elif change == "role":
        db.get(Role, 1).enabled = False
    elif change == "scope":
        db.get(Role, 1).data_scope = DataScope.SELF
    elif change == "receiver":
        db.get(FeedbackRecipient, (41, 2)).active = False
    elif change == "inactive":
        db.get(User, 2).status = UserStatus.DISABLED
    elif change in {"allowlist", "production-allowlist"}:
        if change == "production-allowlist":
            settings.app_env = "production"
        settings.wecom_allowlist = "member_2"  # Test membership is exact.
    elif change == "disabled":
        settings.wecom_enabled = False
    db.commit()
    drain(service)
    row = deliveries(db, task.id)["WECOM"]
    assert (row.status, row.last_error) == ("SKIPPED", expected_error)
    assert not sender.called


def test_worker_retries_clear_transient_failure_with_same_message(worker):
    db, service, _settings, sender, _smtp = worker
    task = queue_event(db)
    service.expand()
    sender.side_effect = [WecomDeliveryError("RETRY", "WECOM_RATE_LIMITED"), None]
    drain(service)
    row = deliveries(db, task.id)["WECOM"]
    assert (row.status, row.attempts, row.last_error) == ("RETRY", 1, "WECOM_RATE_LIMITED")
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    drain(service)
    assert (row.status, row.attempts, row.last_error) == ("SENT", 2, None)
    assert sender.call_args_list[0] == sender.call_args_list[1]


def test_worker_stops_at_retry_limit_without_affecting_site_or_email(worker):
    db, service, _settings, sender, _smtp = worker
    task = queue_event(db)
    service.expand()
    channels = deliveries(db, task.id)
    sender.side_effect = WecomDeliveryError("RETRY", "WECOM_RATE_LIMITED")
    row = channels["WECOM"]
    for attempt in range(1, 6):
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        drain(service)
        assert row.attempts == attempt
        assert row.status == ("RETRY" if attempt < 5 else "FAILED")
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    drain(service)
    assert sender.call_count == 5
    assert channels["EMAIL"].status == channels["SITE"].status == "SENT"


def test_worker_does_not_retry_uncertain_outcomes_or_expired_leases(worker):
    db, service, _settings, sender, _smtp = worker
    during_send = queue_event(db)
    expired = queue_event(db)
    service.expand()
    expired_row = deliveries(db, expired.id)["WECOM"]
    expired_row.status = "SENDING"
    expired_row.attempts = 1
    expired_row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    sender.side_effect = WecomDeliveryError("UNCERTAIN", "WECOM_OUTCOME_UNCERTAIN")
    drain(service)
    uncertain_row = deliveries(db, during_send.id)["WECOM"]
    assert (uncertain_row.status, uncertain_row.last_error) == (
        "UNCERTAIN",
        "WECOM_OUTCOME_UNCERTAIN",
    )
    assert (expired_row.status, expired_row.last_error) == ("UNCERTAIN", "WECOM_LEASE_EXPIRED")
    assert uncertain_row.attempts == expired_row.attempts == 1
    for row in (expired_row, uncertain_row):
        row.next_attempt_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    drain(service)
    assert sender.call_count == 1


def test_wecom_failures_are_not_available_to_the_mail_retry_endpoint(worker):
    db, service, _settings, sender, _smtp = worker
    task = queue_event(db)
    service.expand()
    sender.side_effect = WecomDeliveryError("FAILED", "WECOM_RECIPIENT_REFUSED")
    drain(service)
    row = deliveries(db, task.id)["WECOM"]
    assert (row.status, row.last_error) == ("FAILED", "WECOM_RECIPIENT_REFUSED")
    with pytest.raises(NotFoundError):
        service.retry(row.id, row.attempts)
    assert row.status == "FAILED"

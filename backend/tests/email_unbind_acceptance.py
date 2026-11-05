"""Shared API and SMTP concurrency checks on fresh PostgreSQL/MySQL fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.entities import (
    CollaborationEvent,
    MailPreference,
    Notification,
    NotificationDelivery,
    OperationLog,
    User,
)
from app.services.delivery_service import DeliveryService
from app.services.mail_preferences_service import verification_code

PATH = "/api/v1/me/email-unbind"
PREF = "/api/v1/me/mail-preferences"
VERIFY = "/api/v1/me/email-verification"


def exercise_unbind(fixture, scenario, monkeypatch):
    client, engine, admin_id, admin = fixture
    with Session(engine) as db:
        member = User(
            username="unbind-member",
            display_name="解绑成员",
            password_hash="unused",
            must_change_password=False,
        )
        db.add(member)
        db.commit()
        uid = member.id
    headers = {"Authorization": "Bearer " + create_access_token(uid)}
    user_id, actor = (admin_id, admin) if scenario in ("delivery", "inflight") else (uid, headers)
    client.get(PREF, headers=actor)
    monkeypatch.setattr(get_settings(), "smtp_enabled", True)
    monkeypatch.setattr(get_settings(), "smtp_allowlist", "old@example.test,pending@example.test")
    sent = []
    monkeypatch.setattr(
        "app.services.delivery_service.send_smtp", lambda _message, address: sent.append(address)
    )
    now = datetime.now(UTC)
    with Session(engine) as db:
        user = db.get(User, user_id)
        user.email = None if scenario == "pending" else "old@example.test"
        item = db.get(MailPreference, user_id)
        item.mode = "OFF" if scenario == "off" else "ALL"
        item.verified_email = user.email
        item.verified_at = now - timedelta(days=1) if user.email else None
        item.notice_acknowledged_at = now - timedelta(hours=1)
        item.pending_email = "pending@example.test"
        item.challenge_id = "11111111-2222-3333-4444-555555555555"
        item.challenge_expires_at = now + timedelta(minutes=15)
        item.challenge_user_revision = user.revision
        item.challenge_attempts = 1
        item.requested_at = now
        old_code = verification_code(item.challenge_id)
        db.commit()
        initial_user_revision = user.revision
    before = client.get(PREF, headers=actor).json()

    def unbind(revision=before["revision"]):
        return client.post(PATH, headers=actor, json={"revision": revision})

    def queue():
        f = client.post(
            "/api/v1/feedbacks",
            headers=admin,
            json={
                "title": "解绑投递并发验收",
                "description": "仅隔离测试实例",
                "feedback_type": "OTHER",
                "recipient_ids": [admin_id],
            },
        )
        assert f.status_code == 200, f.text
        with Session(engine) as db:
            pref = db.get(MailPreference, user_id)
            db.add(
                CollaborationEvent(
                    id=pref.challenge_id,
                    entity_type="ACCOUNT",
                    entity_id=user_id,
                    action="VERIFY_EMAIL",
                    actor_id=user_id,
                    recipient_ids=[user_id],
                )
            )
            db.commit()
            DeliveryService(db).expand()
        return f.json()["id"]

    def drain():
        with Session(engine) as db:
            service = DeliveryService(db)
            service.expand()
            while service.deliver_one():
                pass

    if scenario == "rollback":

        def fail_audit(*_args, **_kwargs):
            raise RuntimeError("injected audit failure")

        monkeypatch.setattr("app.services.audit_service.AuditService.log", fail_audit)
        assert unbind().status_code == 500
        assert client.get(PREF, headers=actor).json() == before
        with Session(engine) as db:
            assert db.get(User, user_id).revision == initial_user_revision
            assert db.get(MailPreference, user_id).challenge_id is not None
        return
    if scenario == "race":
        barrier = Barrier(2)

        def contender():
            barrier.wait()
            return unbind()

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: contender(), range(2)))
        assert sorted(r.status_code for r in responses) == [200, 409]
    elif scenario == "inflight":
        queue()
        entered, release, unbind_started = Event(), Event(), Event()

        def block_send(_message, address):
            entered.set()
            assert release.wait(10)
            sent.append(address)

        monkeypatch.setattr("app.services.delivery_service.send_smtp", block_send)

        def do_unbind():
            unbind_started.set()
            return unbind()

        with ThreadPoolExecutor(max_workers=2) as pool:
            sender = pool.submit(drain)
            assert entered.wait(10)
            pending = pool.submit(do_unbind)
            assert unbind_started.wait(2)
            # An SMTP attempt holds the account lock; unbind cannot finish first.
            try:
                with pytest.raises(TimeoutError):
                    pending.result(timeout=0.25)
            finally:
                release.set()
            assert pending.result(timeout=10).status_code == 200
            sender.result(timeout=10)
        count = len(sent)
        drain()
        assert len(sent) == count
    elif scenario == "delivery":
        fid = queue()
        assert unbind().status_code == 200
        drain()
        assert not sent
        with Session(engine) as db:
            emails = list(
                db.scalars(
                    select(NotificationDelivery).where(NotificationDelivery.channel == "EMAIL")
                )
            )
            assert len(emails) >= 2 and all(row.status == "SKIPPED" for row in emails)
            assert all(row.last_error == "PREFERENCE_OR_EMAIL_CHANGED" for row in emails)
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.entity_id == fid, Notification.user_id == user_id)
                )
                >= 1
            )
        # Rebinding the same address must not replay earlier progress messages.
        with Session(engine) as db:
            db.get(MailPreference, user_id).requested_at = now - timedelta(minutes=2)
            db.commit()
        latest = client.get(PREF, headers=actor).json()
        request = client.post(
            VERIFY,
            headers=actor,
            json={"revision": latest["revision"], "email": "old@example.test"},
        )
        assert request.status_code == 200
        with Session(engine) as db:
            code = verification_code(db.get(MailPreference, user_id).challenge_id)
        drain()
        assert sent == ["old@example.test"]
        confirmed = client.post(
            VERIFY + "/confirm",
            headers=actor,
            json={"revision": request.json()["revision"], "code": code},
        )
        assert confirmed.status_code == 200 and confirmed.json()["verified"]
        drain()
        assert sent == ["old@example.test"]
        return
    else:
        # No business role is needed; another account cannot be targeted.
        # SMTP availability does not restrict unbinding.
        assert client.post(PATH, json={"revision": before["revision"]}).status_code == 401
        assert client.post(PATH, headers=actor, json={"revision": 0}).status_code == 422
        assert (
            client.post(
                PATH, headers=actor, json={"revision": before["revision"], "user_id": admin_id}
            ).status_code
            == 422
        )
        assert unbind(before["revision"] + 1).status_code == 409
        other = client.get(PREF, headers=admin).json()
        monkeypatch.setattr(get_settings(), "smtp_enabled", False)
        result = unbind()
        assert result.status_code == 200, result.text
        assert client.get(PREF, headers=admin).json() == {**other, "smtp_enabled": False}

    after = client.get(PREF, headers=actor).json()
    assert after == {
        **before,
        "revision": before["revision"] + 1,
        "email": None,
        "verified": False,
        "pending_email": None,
        "smtp_enabled": get_settings().smtp_enabled,
    }
    assert unbind().status_code == 409
    assert unbind(after["revision"]).json() == after
    with Session(engine) as db:
        pref = db.get(MailPreference, user_id)
        assert all(
            getattr(pref, key) is None
            for key in (
                "verified_email",
                "verified_at",
                "pending_email",
                "challenge_id",
                "challenge_expires_at",
                "challenge_user_revision",
            )
        )
        assert pref.challenge_attempts == 0 and pref.requested_at is not None
        assert pref.notice_acknowledged_at is not None
        assert db.get(User, user_id).revision == initial_user_revision + 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(OperationLog.action == "EMAIL_UNBOUND", OperationLog.operator_id == user_id)
            )
            == 1
        )
    other_device = {"Authorization": "Bearer " + create_access_token(user_id)}
    assert client.get(PREF, headers=other_device).json() == after
    old = client.post(
        VERIFY + "/confirm", headers=actor, json={"revision": after["revision"], "code": old_code}
    )
    assert old.status_code == 409
    if scenario in ("account", "off", "pending"):
        monkeypatch.setattr(get_settings(), "smtp_enabled", True)
        assert (
            client.post(
                VERIFY,
                headers=actor,
                json={"revision": after["revision"], "email": "old@example.test"},
            ).status_code
            == 429
        )

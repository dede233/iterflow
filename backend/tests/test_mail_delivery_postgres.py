# ruff: noqa: F811
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from socketserver import StreamRequestHandler, ThreadingTCPServer
from threading import Thread

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_collaboration_postgres import collaboration_api, create_feedback  # noqa: F401

from app.core.config import get_settings
from app.models.entities import (
    CollaborationEvent,
    FeedbackRecipient,
    MailPreference,
    Notification,
    NotificationDelivery,
    User,
)
from app.services.collaboration_service import CollaborationService
from app.services.delivery_service import DeliveryService
from app.services.mail_preferences_service import verification_code


@pytest.fixture
def smtp_sink(monkeypatch):
    messages = []

    class Handler(StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 local test SMTP\r\n")
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                verb = line.split(b" ", 1)[0].strip().upper()
                if verb == b"DATA":
                    self.wfile.write(b"354 data\r\n")
                    body = []
                    while (line := self.rfile.readline()) not in (b".\r\n", b""):
                        body.append(line)
                    messages.append(BytesParser(policy=policy.default).parsebytes(b"".join(body)))
                    self.wfile.write(b"250 accepted\r\n")
                elif verb == b"QUIT":
                    self.wfile.write(b"221 bye\r\n")
                    break
                else:
                    self.wfile.write(b"250 OK\r\n")

    server = ThreadingTCPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = get_settings()
    for key, value in dict(
        smtp_enabled=True,
        smtp_host="127.0.0.1",
        smtp_port=server.server_address[1],
        smtp_security="none",
        smtp_allowlist="person2@example.test,changed@example.test",
        smtp_from="iterflow@example.test",
    ).items():
        monkeypatch.setattr(settings, key, value)
    yield messages
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def drain(engine):
    with Session(engine) as db:
        service = DeliveryService(db)
        service.expand()
        for _ in range(50):
            if not service.deliver_one():
                break


def verify(client, headers, engine):
    settings = client.get("/api/v1/me/mail-preferences", headers=headers[2]).json()
    response = client.post(
        "/api/v1/me/email-verification",
        headers=headers[2],
        json={"revision": settings["revision"], "email": "person2@example.test"},
    )
    assert response.status_code == 200, response.text
    revision = response.json()["revision"]
    with Session(engine) as db:
        code = verification_code(db.get(MailPreference, 2).challenge_id)
    drain(engine)
    response = client.post(
        "/api/v1/me/email-verification/confirm",
        headers=headers[2],
        json={"revision": revision, "code": code},
    )
    assert response.status_code == 200, response.text
    assert response.json()["verified"]
    return response.json()


def test_verified_mail_site_dedup_and_email_change(collaboration_api, smtp_sink):
    client, headers, engine = collaboration_api
    preferences = verify(client, headers, engine)
    assert len(smtp_sink) == 1 and "验证码" in smtp_sink[0].get_content()
    first = create_feedback(client, headers).json()
    drain(engine)
    drain(engine)
    assert len(smtp_sink) == 2 and "有反馈需要处理" in smtp_sink[1]["Subject"]
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.entity_id == first["id"])
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(NotificationDelivery)
                .where(
                    NotificationDelivery.status == "SENT", NotificationDelivery.channel == "EMAIL"
                )
            )
            == 2
        )
    second = create_feedback(client, headers).json()
    with Session(engine) as db:
        DeliveryService(db).expand()
        db.get(User, 2).email = "changed@example.test"
        db.commit()
    drain(engine)
    assert len(smtp_sink) == 2
    # Existing pending work is not redirected to a changed mailbox.
    with Session(engine) as db:
        delivery = db.scalar(
            select(NotificationDelivery)
            .join(CollaborationEvent)
            .where(
                CollaborationEvent.entity_id == second["id"],
                CollaborationEvent.entity_type == "FEEDBACK",
                NotificationDelivery.user_id == 2,
                NotificationDelivery.channel == "EMAIL",
            )
        )
        assert delivery.status == "SKIPPED"
    response = client.put(
        "/api/v1/me/mail-preferences",
        headers=headers[2],
        json={"revision": preferences["revision"] - 1, "mode": "ALL"},
    )
    assert response.status_code == 409


def test_recipient_removal_revokes_queued_notifications(collaboration_api, smtp_sink):
    client, headers, engine = collaboration_api
    verify(client, headers, engine)
    feedback = create_feedback(client, headers).json()
    with Session(engine) as db:
        DeliveryService(db).expand()
        db.get(FeedbackRecipient, (feedback["id"], 2)).active = False
        db.commit()
    drain(engine)
    assert len(smtp_sink) == 1
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Notification).where(Notification.user_id == 2)
            )
            == 0
        )


def test_timeout_restarts_with_stable_message_id_and_bounded_retry(
    collaboration_api,
    smtp_sink,
    monkeypatch,
):
    client, headers, engine = collaboration_api
    verify(client, headers, engine)
    create_feedback(client, headers)
    message_ids = []

    def timeout(message, _address):
        message_ids.append(message["Message-ID"])
        raise TimeoutError("secret-bearing SMTP response must not be stored")

    monkeypatch.setattr("app.services.delivery_service.send_smtp", timeout)
    drain(engine)
    with Session(engine) as db:
        row = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.status == "UNCERTAIN")
        )
        assert row.last_error == "SMTP_OUTCOME_UNCERTAIN" and row.attempts == 1
        rid = row.id
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    drain(engine)
    assert len(message_ids) == 2 and message_ids[0] == message_ids[1]
    with Session(engine) as db:
        row = db.get(NotificationDelivery, rid)
        row.status = "SENDING"
        row.attempts = 5
        row.next_attempt_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
    drain(engine)
    with Session(engine) as db:
        row = db.get(NotificationDelivery, rid)
        assert row.status == "FAILED" and row.last_error == "RETRY_LIMIT"
        assert "secret" not in (row.last_error or "")


def test_verification_attempt_limit_and_transactional_event_rollback(collaboration_api, smtp_sink):
    client, headers, engine = collaboration_api
    client.get("/api/v1/me/mail-preferences", headers=headers[2])
    response = client.post(
        "/api/v1/me/email-verification",
        headers=headers[2],
        json={"revision": 1, "email": "person2@example.test"},
    )
    assert response.status_code == 200
    with Session(engine) as db:
        right = verification_code(db.get(MailPreference, 2).challenge_id)
    wrong = "111111" if right != "111111" else "222222"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/me/email-verification/confirm",
                headers=headers[2],
                json={"revision": 2, "code": wrong},
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/api/v1/me/email-verification/confirm",
            headers=headers[2],
            json={"revision": 2, "code": right},
        ).status_code
        == 409
    )
    with Session(engine) as db:
        CollaborationService(db).event("FEEDBACK", 999, "RECIPIENT_ADDED", 1, [2])
        db.flush()
        db.rollback()
        assert (
            db.scalar(
                select(func.count())
                .select_from(CollaborationEvent)
                .where(CollaborationEvent.entity_id == 999)
            )
            == 0
        )
    assert client.get("/api/v1/admin/mail-deliveries", headers=headers[2]).status_code == 403


def test_off_preference_keeps_site_and_permanent_failure_needs_retry(
    collaboration_api, smtp_sink, monkeypatch
):
    import smtplib

    client, headers, engine = collaboration_api
    pref = verify(client, headers, engine)
    assert (
        client.put(
            "/api/v1/me/mail-preferences",
            headers=headers[2],
            json={"revision": pref["revision"], "mode": "OFF"},
        ).status_code
        == 200
    )
    create_feedback(client, headers)
    drain(engine)
    assert len(smtp_sink) == 1
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Notification).where(Notification.user_id == 2)
            )
            == 1
        )
        db.get(MailPreference, 2).mode = "ALL"
        db.commit()
    create_feedback(client, headers)

    def refuse(*_args):
        raise smtplib.SMTPResponseException(550, b"private recipient info")

    monkeypatch.setattr("app.services.delivery_service.send_smtp", refuse)
    drain(engine)
    with Session(engine) as db:
        row = db.scalar(select(NotificationDelivery).where(NotificationDelivery.status == "FAILED"))
        assert row.last_error == "SMTP_550"
        assert row.attempts == 1
        response = DeliveryService(db).retry(row.id, row.attempts)
        assert response.status == "PENDING"
        # A manual retry still performs authorization; disabling the account cancels it.
        db.get(User, 2).status = "DISABLED"
        db.commit()
    drain(engine)
    with Session(engine) as db:
        row = db.get(NotificationDelivery, response.id)
        assert row.status == "SKIPPED" and row.last_error == "ACCESS_REVOKED"

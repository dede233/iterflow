# ruff: noqa: F811
import re

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_collaboration_postgres import collaboration_api  # noqa: F401
from test_mail_delivery_postgres import drain, smtp_sink  # noqa: F401

from app.core.audit_context import AuditContext, audit_context, get_audit_context
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import (
    CollaborationEvent,
    MailPreference,
    NotificationDelivery,
    OperationLog,
    User,
)
from app.services.mail_preferences_service import MailPreferencesService, verification_code

ACCOUNT_EMAIL = "person2@example.test"
INITIAL_PASSWORD = "initial-invite-test-password"


def invite(engine) -> str:
    with Session(engine) as db:
        user = db.get(User, 2)
        user.email = ACCOUNT_EMAIL
        user.password_hash = hash_password(INITIAL_PASSWORD)
        user.must_change_password = True
        db.commit()
        with audit_context(AuditContext(operator_id=3, request_id="test-invite")):
            MailPreferencesService(db).invite(user, user.revision, 1)
            assert get_audit_context().operator_id == 3

    with Session(engine) as db:
        preference = db.get(MailPreference, 2)
        event = db.get(CollaborationEvent, preference.challenge_id)
        assert preference.pending_email == ACCOUNT_EMAIL and preference.verified_email is None
        assert event.action == "VERIFY_EMAIL" and event.actor_id == 1
        assert event.entity_id == 2 and event.recipient_ids == [2]
        audit = db.scalar(
            select(OperationLog).where(OperationLog.action == "EMAIL_VERIFICATION_INVITE")
        )
        assert audit.operator_id == 1 and audit.entity_id == 2
        assert audit.request_id == "test-invite"
        assert audit.after_data is None
        return event.id


def complete_initial_password_change(client):
    login = client.post(
        "/api/v1/auth/login", json={"username": "user2", "password": INITIAL_PASSWORD}
    )
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"]
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/me/mail-preferences", headers=headers).status_code == 403
    password_change = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": INITIAL_PASSWORD,
            "new_password": "new-invite-test-password",
        },
    )
    assert password_change.status_code == 200, password_change.text
    assert not password_change.json()["must_change_password"]
    return {"Authorization": f"Bearer {password_change.json()['access_token']}"}


@pytest.mark.parametrize("deliver_before_password_change", [True, False])
def test_admin_invitation_is_usable_after_first_login(
    collaboration_api, smtp_sink, monkeypatch, deliver_before_password_change
):
    client, _, engine = collaboration_api
    profile_url = "https://iterflow.example.test:8444/work/#/profile#mail-notifications"
    monkeypatch.setattr(
        get_settings(), "app_public_url", "https://iterflow.example.test:8444/work/"
    )
    challenge_id = invite(engine)
    if deliver_before_password_change:
        drain(engine)
        assert len(smtp_sink) == 1
    headers = complete_initial_password_change(client)
    drain(engine)
    assert len(smtp_sink) == 1
    message = smtp_sink[0]
    assert message["To"] == ACCOUNT_EMAIL
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    code = re.search(r"(?<!\d)\d{6}(?!\d)", plain).group()
    assert code == verification_code(challenge_id)
    assert profile_url in plain and f'href="{profile_url}"' in html
    assert INITIAL_PASSWORD not in plain and INITIAL_PASSWORD not in html
    preferences = client.get("/api/v1/me/mail-preferences", headers=headers).json()
    assert not preferences["verified"] and preferences["pending_email"] == ACCOUNT_EMAIL
    confirmed = client.post(
        "/api/v1/me/email-verification/confirm",
        headers=headers,
        json={"revision": preferences["revision"], "code": code},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["verified"] and confirmed.json()["email"] == ACCOUNT_EMAIL


def test_initial_password_change_does_not_revive_an_older_account_revision(
    collaboration_api, smtp_sink
):
    client, _, engine = collaboration_api
    challenge_id = invite(engine)
    with Session(engine) as db:
        user = db.get(User, 2)
        user.display_name = "Updated user"
        user.revision += 1
        db.commit()

    headers = complete_initial_password_change(client)
    drain(engine)
    assert not smtp_sink
    preferences = client.get("/api/v1/me/mail-preferences", headers=headers).json()
    invalid = client.post(
        "/api/v1/me/email-verification/confirm",
        headers=headers,
        json={"revision": preferences["revision"], "code": verification_code(challenge_id)},
    )
    assert invalid.status_code == 409, invalid.text


def test_incomplete_historical_verification_can_be_reinvited(collaboration_api, smtp_sink):
    client, headers, engine = collaboration_api
    with Session(engine) as db:
        user = db.get(User, 2)
        user.email = ACCOUNT_EMAIL
        db.add(MailPreference(user_id=user.id, verified_email=ACCOUNT_EMAIL))
        db.commit()

    before = client.get("/api/v1/me/mail-preferences", headers=headers[2]).json()
    assert before["email"] == ACCOUNT_EMAIL and not before["verified"]
    with Session(engine) as db:
        user = db.get(User, 2)
        MailPreferencesService(db).invite(user, user.revision, 1)
    after = client.get("/api/v1/me/mail-preferences", headers=headers[2]).json()
    assert after["pending_email"] == ACCOUNT_EMAIL and not after["verified"]
    drain(engine)
    assert len(smtp_sink) == 1 and smtp_sink[0]["To"] == ACCOUNT_EMAIL


def test_worker_skips_an_exhausted_verification_challenge(collaboration_api, smtp_sink):
    _, _, engine = collaboration_api
    event_id = invite(engine)
    with Session(engine) as db:
        db.get(MailPreference, 2).challenge_attempts = 5
        db.commit()

    drain(engine)
    assert not smtp_sink
    with Session(engine) as db:
        delivery = db.scalar(
            select(NotificationDelivery).where(NotificationDelivery.event_id == event_id)
        )
        assert delivery.status == "SKIPPED"

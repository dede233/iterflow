"""Shared HTTP and database acceptance for administrator email invitations."""

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.entities import CollaborationEvent, MailPreference, NotificationDelivery, User
from app.services.delivery_service import DeliveryService

USERS = "/api/v1/users"
PREFERENCES = "/api/v1/me/mail-preferences"
CONFIRM = "/api/v1/me/email-verification/confirm"


def exercise_email_invitation(fixture, scenario, monkeypatch):
    client, engine, admin_id, admin = fixture
    username = f"invite-{scenario}"
    email = f"{username}@example.test"
    monkeypatch.setattr(get_settings(), "smtp_enabled", True)
    monkeypatch.setattr(get_settings(), "smtp_allowlist", email)
    sent = []

    def capture_message(message, address):
        assert address == email
        assert message["To"] == email
        text = message.get_body(preferencelist=("plain",)).get_content()
        match = re.search(r"(?<!\d)\d{6}(?!\d)", text)
        assert match
        sent.append(match.group())

    monkeypatch.setattr("app.services.delivery_service.send_smtp", capture_message)

    if scenario == "automatic":
        password = "Initial-test-password!"
        created = client.post(
            USERS,
            headers=admin,
            json={
                "username": username,
                "display_name": "新账号",
                "email": email,
                "password": password,
            },
        )
        assert created.status_code == 200, created.text
        account = created.json()
        assert account["verification_invitation"] == "QUEUED"
        assert account["email_verification_status"] == "PENDING"
        user_id = account["id"]
        url = f"{USERS}/{user_id}"
    else:
        with Session(engine) as db:
            user = User(
                username=username,
                display_name="历史账号",
                email=email,
                password_hash="unused-test-digest",
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            user_id = user.id
            revision = user.revision

        url = f"{USERS}/{user_id}"
        legacy = client.get(url, headers=admin)
        assert legacy.status_code == 200, legacy.text
        assert legacy.json()["email_verification_status"] == "UNVERIFIED"
        with Session(engine) as db:
            assert db.get(MailPreference, user_id) is None

        barrier = Barrier(2)

        def invite():
            barrier.wait(timeout=10)
            return client.post(
                f"{url}/email-verification", headers=admin, json={"revision": revision}
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [pool.submit(invite) for _ in range(2)]
            results = [response.result(timeout=20) for response in responses]
        assert sorted(response.status_code for response in results) == [204, 429], [
            response.text for response in results
        ]

    assert sent == []
    with Session(engine) as db:
        outbox = db.scalars(
            select(CollaborationEvent).where(
                CollaborationEvent.entity_type == "ACCOUNT",
                CollaborationEvent.entity_id == user_id,
                CollaborationEvent.action == "VERIFY_EMAIL",
            )
        ).one()
        assert outbox.actor_id == admin_id
        assert outbox.recipient_ids == [user_id]
        outbox_id = outbox.id
        preference = db.get(MailPreference, user_id)
        assert preference.challenge_id == outbox_id
        assert preference.pending_email == email
        assert preference.verified_email is None

    if scenario == "automatic":
        logged_in = client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["must_change_password"]
        initial_headers = {"Authorization": "Bearer " + logged_in.json()["access_token"]}
        blocked = client.get(PREFERENCES, headers=initial_headers)
        assert blocked.status_code == 403
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=initial_headers,
            json={"current_password": password, "new_password": "Changed-test-password!"},
        )
        assert changed.status_code == 200
        assert not changed.json()["must_change_password"]
        member = {"Authorization": "Bearer " + changed.json()["access_token"]}
        with Session(engine) as db:
            preference = db.get(MailPreference, user_id)
            assert preference.challenge_id == outbox_id
            assert preference.challenge_user_revision == db.get(User, user_id).revision
    else:
        member = {"Authorization": "Bearer " + create_access_token(user_id)}

    with Session(engine) as db:
        service = DeliveryService(db)
        assert service.expand() == 1
        assert service.deliver_one()
        delivery = db.scalars(
            select(NotificationDelivery).where(NotificationDelivery.event_id == outbox_id)
        ).one()
        assert (delivery.channel, delivery.queued_email, delivery.status) == (
            "EMAIL",
            email,
            "SENT",
        )
    assert len(sent) == 1

    pending = client.get(url, headers=admin)
    assert pending.status_code == 200, pending.text
    assert pending.json()["email_verification_status"] == "PENDING"
    pref = client.get(PREFERENCES, headers=member)
    assert pref.status_code == 200, pref.text
    assert not pref.json()["verified"]
    assert pref.json()["pending_email"] == email
    confirmed = client.post(
        CONFIRM, headers=member, json={"revision": pref.json()["revision"], "code": sent[0]}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["verified"]

    listed = client.get(USERS, headers=admin)
    assert listed.status_code == 200, listed.text
    account = next(user for user in listed.json()["items"] if user["id"] == user_id)
    assert account["email_verification_status"] == "VERIFIED"
    assert account["email"] == email
    already_verified = client.post(
        f"{url}/email-verification", headers=admin, json={"revision": account["revision"]}
    )
    assert already_verified.status_code == 409, already_verified.text

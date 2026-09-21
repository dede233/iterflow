from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, hash_password, verify_password
from app.main import app
from app.models.entities import (
    OperationLog,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import UserStatus


@pytest.fixture
def auth_api(tmp_path: Path) -> Iterator[tuple[TestClient, Session, User]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-api.db'}", connect_args={"check_same_thread": False}
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        RefreshSession.__table__,
        OperationLog.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission, OperationLog):
        counter = iter(range(1, 1000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        user = User(
            username="auth-user",
            display_name="Auth User",
            password_hash=hash_password("initial-password"),
            must_change_password=False,
        )
        session.add(user)
        session.commit()

        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, session, user
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def _login(
    client: TestClient,
    *,
    password: str = "initial-password",
    must_change_password: bool = False,
) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        headers={"User-Agent": "IterFlow-Auth-Test/1.0"},
        json={"username": "auth-user", "password": password},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["must_change_password"] is must_change_password
    return payload


def test_login_me_and_failed_login_are_audited_without_secrets(auth_api):
    client, session, user = auth_api

    token_pair = _login(client)
    access_headers = {"Authorization": f"Bearer {token_pair['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=access_headers)

    assert me.status_code == 200
    assert me.json() == {
        "id": user.id,
        "username": "auth-user",
        "display_name": "Auth User",
        "email": None,
        "status": "ACTIVE",
        "revision": 1,
        "must_change_password": False,
        "data_scope": "SELF",
        "role_ids": [],
        "permission_codes": [],
    }
    assert decode_token(token_pair["refresh_token"], "refresh")["sid"]
    assert decode_token(token_pair["refresh_token"], "refresh")["jti"]

    denied = client.post(
        "/api/v1/auth/login",
        json={"username": "auth-user", "password": "wrong-password"},
    )
    assert denied.status_code == 401

    entries = session.scalars(select(OperationLog).order_by(OperationLog.id)).all()
    assert [entry.action for entry in entries] == ["LOGIN", "LOGIN_FAILED"]
    assert entries[0].operator_id == user.id
    assert entries[0].user_agent == "IterFlow-Auth-Test/1.0"
    audit_payload = str([(entry.before_data, entry.after_data) for entry in entries])
    assert "initial-password" not in audit_payload
    assert "wrong-password" not in audit_payload
    assert token_pair["access_token"] not in audit_payload
    assert token_pair["refresh_token"] not in audit_payload


def test_refresh_token_is_persisted_rotated_and_old_token_is_rejected(auth_api):
    client, session, _user = auth_api

    initial = _login(client)
    # A refresh credential is never accepted as an Access bearer credential.
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {initial['refresh_token']}"},
        ).status_code
        == 401
    )
    old_claims = decode_token(initial["refresh_token"], "refresh")
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": initial["refresh_token"]}
    )

    assert refreshed.status_code == 200
    refreshed_pair = refreshed.json()
    assert refreshed_pair["refresh_token"] != initial["refresh_token"]
    old_session = session.get(RefreshSession, old_claims["sid"])
    assert old_session is not None
    assert old_session.revoked_reason == "REFRESHED"
    assert old_session.revoked_at is not None

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": initial["refresh_token"]})
    assert replay.status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refreshed_pair["refresh_token"]}
        ).status_code
        == 200
    )


def test_logout_revokes_session_and_disabled_user_cannot_refresh_or_use_access_token(auth_api):
    client, session, user = auth_api

    logged_in = _login(client)
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": logged_in["refresh_token"]})
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": logged_in["refresh_token"]}
        ).status_code
        == 401
    )

    active_pair = _login(client)
    user.status = UserStatus.DISABLED
    session.commit()
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": active_pair["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {active_pair['access_token']}"}
        ).status_code
        == 401
    )
    entries = session.scalars(select(OperationLog).order_by(OperationLog.id)).all()
    assert "LOGOUT" in [entry.action for entry in entries]


def test_change_password_revokes_old_sessions_and_returns_a_fresh_session(auth_api):
    client, session, user = auth_api

    previous = _login(client)
    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {previous['access_token']}"},
        json={"current_password": "initial-password", "new_password": "changed-password"},
    )

    assert changed.status_code == 200
    replacement = changed.json()
    assert replacement["must_change_password"] is False
    assert verify_password("changed-password", user.password_hash)
    assert user.revision == 2
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": previous["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": replacement["refresh_token"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "auth-user", "password": "initial-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "auth-user", "password": "changed-password"},
        ).status_code
        == 200
    )

    password_log = session.scalar(
        select(OperationLog).where(OperationLog.action == "PASSWORD_CHANGE")
    )
    assert password_log is not None
    assert password_log.before_data == {"must_change_password": False}
    assert password_log.after_data == {"must_change_password": False}
    audit_payload = str((password_log.before_data, password_log.after_data))
    assert "initial-password" not in audit_payload
    assert "changed-password" not in audit_payload


def test_must_change_password_is_exposed_and_blocks_other_protected_routes(auth_api):
    client, session, user = auth_api
    user.must_change_password = True
    session.commit()

    token_pair = _login(client, must_change_password=True)
    assert token_pair["must_change_password"] is True
    headers = {"Authorization": f"Bearer {token_pair['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    blocked = client.get("/api/v1/roles", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == 40310

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "initial-password", "new_password": "changed-password"},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False

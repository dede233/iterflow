from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import Notification, Permission, Role, RolePermission, User, UserRole

Fixture = tuple[TestClient, Session, dict[str, str], dict[str, str]]


@pytest.fixture
def notification_api(tmp_path: Path) -> Iterator[Fixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'notifications.db'}", connect_args={"check_same_thread": False}
    )
    for model in (User, Role, Permission, UserRole, RolePermission, Notification):
        model.__table__.create(engine)
    with Session(engine) as db:
        db.add_all(
            [
                User(
                    id=i,
                    username=f"user-{i}",
                    display_name=f"User {i}",
                    password_hash="unused",
                    must_change_password=False,
                )
                for i in (1, 2)
            ]
        )
        db.commit()
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                yield (
                    client,
                    db,
                    {"Authorization": f"Bearer {create_access_token(1)}"},
                    {"Authorization": f"Bearer {create_access_token(2)}"},
                )
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


def seed(db: Session, *, a: int = 3, b: int = 2, read: int = 1) -> None:
    db.add_all(
        [
            Notification(
                id=i + 1,
                user_id=1 if i < a + read else 2,
                title=f"Notice {i}",
                content="content",
                read_at=datetime(2026, 1, 1, tzinfo=UTC) if a <= i < a + read else None,
            )
            for i in range(a + b + read)
        ]
    )
    db.commit()


def test_count_zero_and_auth_required(notification_api: Fixture):
    client, _, a, _ = notification_api
    assert client.get("/api/v1/notifications/unread-count", headers=a).json() == {"unread_count": 0}
    for method, path in (("GET", "unread-count"), ("POST", "read-all")):
        assert client.request(method, f"/api/v1/notifications/{path}").status_code == 401


def test_count_and_list_isolate_users_without_business_permissions(notification_api: Fixture):
    client, db, a, b = notification_api
    seed(db)
    assert client.get("/api/v1/notifications/unread-count", headers=a).json() == {"unread_count": 3}
    assert client.get("/api/v1/notifications/unread-count", headers=b).json() == {"unread_count": 2}
    assert len(client.get("/api/v1/notifications?unread_only=true", headers=a).json()) == 3
    assert len(client.get("/api/v1/notifications", headers=a).json()) == 4


def test_count_exceeds_list_limit(notification_api: Fixture):
    client, db, a, _ = notification_api
    seed(db, a=125)
    assert len(client.get("/api/v1/notifications", headers=a).json()) == 100
    assert client.get("/api/v1/notifications/unread-count", headers=a).json() == {
        "unread_count": 125
    }
    assert client.post("/api/v1/notifications/read-all", headers=a).json() == {"updated_count": 125}


def test_read_all_static_route_is_owned_and_idempotent(notification_api: Fixture):
    client, db, a, b = notification_api
    seed(db)
    before = db.get(Notification, 4).read_at
    response = client.post("/api/v1/notifications/read-all", headers=a)
    assert response.status_code == 200
    assert response.json() == {"updated_count": 3}
    assert client.get("/api/v1/notifications/unread-count", headers=a).json() == {"unread_count": 0}
    assert client.get("/api/v1/notifications/unread-count", headers=b).json() == {"unread_count": 2}
    assert db.get(Notification, 4).read_at == before
    assert client.post("/api/v1/notifications/read-all", headers=a).json() == {"updated_count": 0}


def test_single_read_does_not_leak_or_modify_other_user(notification_api: Fixture):
    client, db, a, b = notification_api
    seed(db)
    for notification_id in (5, 999):
        assert client.post(f"/api/v1/notifications/{notification_id}/read", headers=a).json() == {
            "ok": True
        }
    assert client.get("/api/v1/notifications/unread-count", headers=b).json() == {"unread_count": 2}
    assert client.post("/api/v1/notifications/1/read", headers=a).json() == {"ok": True}
    before = db.get(Notification, 1).read_at
    assert client.post("/api/v1/notifications/1/read", headers=a).json() == {"ok": True}
    assert db.get(Notification, 1).read_at == before
    assert client.get("/api/v1/notifications/unread-count", headers=a).json() == {"unread_count": 2}

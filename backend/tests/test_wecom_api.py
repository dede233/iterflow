from collections.abc import Iterator
from itertools import count
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    WecomPreference,
)
from app.models.enums import DataScope, UserStatus

PREFERENCES = "/api/v1/me/wecom-preferences"
ApiFixture = tuple[TestClient, sessionmaker[Session]]


def binding(user_id: int) -> str:
    return f"/api/v1/users/{user_id}/wecom-binding"


def auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def wecom_api(tmp_path: Path, monkeypatch) -> Iterator[ApiFixture]:
    monkeypatch.setattr(get_settings(), "wecom_enabled", False)
    monkeypatch.setattr(get_settings(), "wecom_corp_id", "ww-corp-one")
    engine = create_engine(f"sqlite:///{tmp_path / 'wecom.db'}")
    sessions = sessionmaker(engine, expire_on_commit=False, autoflush=False)
    for model in (User, Role, Permission, RolePermission, UserRole, WecomPreference, OperationLog):
        model.__table__.create(engine)
    audit_ids = count(1)

    def assign_audit_id(_mapper, _connection, target):
        target.id = next(audit_ids)

    with sessions.begin() as db:
        db.add_all(
            User(
                id=user_id,
                username=f"user-{user_id}",
                display_name=f"User {user_id}",
                password_hash="unused",
                must_change_password=False,
            )
            for user_id in range(1, 5)
        )
        db.add_all(
            [
                Role(
                    id=1,
                    code="SUPER_ADMIN",
                    name="Super Admin",
                    is_system=True,
                    data_scope=DataScope.ALL,
                ),
                Role(id=2, code="EDITOR", name="Editor", data_scope=DataScope.ALL),
                Permission(id=1, code="sys.user.edit", name="Edit User"),
            ]
        )
        db.flush()
        db.add_all(
            [
                UserRole(user_id=1, role_id=1),
                UserRole(user_id=4, role_id=2),
                RolePermission(role_id=1, permission_id=1),
                RolePermission(role_id=2, permission_id=1),
            ]
        )

    def session_override():
        with sessions() as db:
            yield db

    event.listen(OperationLog, "before_insert", assign_audit_id)
    app.dependency_overrides[get_db] = session_override
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.pop(get_db)
        event.remove(OperationLog, "before_insert", assign_audit_id)
        engine.dispose()


def test_wecom_reads_are_scoped_and_do_not_create_settings(wecom_api: ApiFixture):
    client, sessions = wecom_api
    assert client.get(PREFERENCES).status_code == 401
    assert client.get(binding(2)).status_code == 401
    assert client.get(binding(2), headers=auth(2)).status_code == 403
    assert client.get(binding(2), headers=auth(4)).status_code == 403
    assert client.get(binding(999), headers=auth(1)).status_code == 404
    expected = {"revision": 0, "member_user_id": None, "mode": "OFF", "enabled": False}
    assert client.get(PREFERENCES, headers=auth(2)).json() == expected
    assert client.get(binding(2), headers=auth(1)).json() == expected
    with sessions() as db:
        assert db.get(WecomPreference, 2) is None
        assert db.scalar(select(OperationLog)) is None


def test_wecom_binding_and_personal_opt_in_share_revision(wecom_api: ApiFixture, monkeypatch):
    client, sessions = wecom_api
    monkeypatch.setattr(get_settings(), "wecom_enabled", True)

    def set_mode(revision: int, mode: str):
        return client.put(PREFERENCES, headers=auth(2), json={"revision": revision, "mode": mode})

    def set_member(revision: int, member_user_id: str | None):
        return client.put(
            binding(2),
            headers=auth(1),
            json={"revision": revision, "member_user_id": member_user_id},
        )

    assert set_mode(0, "TASKS").status_code == 409
    created = set_member(0, "Mixed.Case_01")
    assert created.status_code == 200
    assert created.json() == {
        "revision": 1,
        "member_user_id": "Mixed.Case_01",
        "mode": "OFF",
        "enabled": True,
    }
    stale = set_mode(0, "TASKS")
    assert stale.status_code == 409
    assert stale.json()["data"] == {"current_revision": 1}
    assert set_mode(1, "TASKS").json()["mode"] == "TASKS"
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        old_binding = item.binding_id
        old_eligibility = item.eligible_since
        assert item.member_key == "mixed.case_01"
        assert old_binding and old_eligibility
    assert set_member(2, "Mixed.Case_01").json()["mode"] == "TASKS"
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        assert item.binding_id == old_binding
        assert item.eligible_since == old_eligibility
    stale = set_member(2, "New.MEMBER")
    assert stale.status_code == 409
    assert stale.json()["data"] == {"current_revision": 3}
    assert set_member(3, "New.MEMBER").json()["mode"] == "OFF"
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        assert item.binding_id and item.binding_id != old_binding
        assert item.eligible_since is None
    assert set_mode(4, "ALL").json()["mode"] == "ALL"
    assert set_member(5, None).json() == {
        "revision": 6,
        "member_user_id": None,
        "mode": "OFF",
        "enabled": True,
    }
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        assert item.member_key is None and item.binding_id is None and item.eligible_since is None
        audits = db.scalars(select(OperationLog).order_by(OperationLog.id)).all()
        assert [audit.operator_id for audit in audits] == [1, 2, 1, 1, 2, 1]
        assert all(audit.entity_id == 2 for audit in audits)
        assert {audit.action for audit in audits} == {"WECOM_BINDING", "WECOM_PREFERENCE"}
        for audit in audits:
            data = str((audit.before_data, audit.after_data))
            assert "Mixed.Case_01" not in data and "New.MEMBER" not in data


def test_wecom_member_id_validation_and_unique_conflict(wecom_api: ApiFixture):
    client, sessions = wecom_api
    for value in ("", " abnormal", "member\n", "用户", "z" * 65):
        response = client.put(
            binding(2), headers=auth(1), json={"revision": 0, "member_user_id": value}
        )
        assert response.status_code == 422
    assert (
        client.put(
            binding(2), headers=auth(4), json={"revision": 0, "member_user_id": "Team-01"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            binding(2), headers=auth(1), json={"revision": 0, "member_user_id": "Team-01"}
        ).status_code
        == 200
    )
    duplicate = client.put(
        binding(3), headers=auth(1), json={"revision": 0, "member_user_id": "team-01"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["data"] is None
    assert "Team-01" not in duplicate.text and "team-01" not in duplicate.text
    with sessions.begin() as db:
        assert db.get(WecomPreference, 3) is None
        db.get(User, 2).status = UserStatus.DISABLED
    assert client.get(PREFERENCES, headers=auth(2)).status_code == 401
    assert (
        client.put(
            binding(2), headers=auth(1), json={"revision": 1, "member_user_id": "Team-02"}
        ).status_code
        == 409
    )
    assert (
        client.put(
            binding(2), headers=auth(1), json={"revision": 1, "member_user_id": None}
        ).status_code
        == 200
    )
    assert (
        client.put(
            binding(3), headers=auth(1), json={"revision": 0, "member_user_id": "team-01"}
        ).status_code
        == 200
    )


def test_wecom_binding_requires_enabled_builtin_super_admin_with_all_scope(wecom_api: ApiFixture):
    client, sessions = wecom_api
    for variant in ({"enabled": False}, {"is_system": False}, {"data_scope": DataScope.SELF}):
        with sessions.begin() as db:
            role = db.get(Role, 1)
            role.enabled = True
            role.is_system = True
            role.data_scope = DataScope.ALL
            for property_name, value in variant.items():
                setattr(role, property_name, value)
        assert client.get(binding(2), headers=auth(1)).status_code == 403
        assert (
            client.put(
                binding(2), headers=auth(1), json={"revision": 0, "member_user_id": "Team-01"}
            ).status_code
            == 403
        )


def test_wecom_binding_is_pinned_to_the_configured_corporation(wecom_api: ApiFixture, monkeypatch):
    client, sessions = wecom_api

    def bind(user_id: int, revision: int, member_user_id: str | None):
        return client.put(
            binding(user_id),
            headers=auth(1),
            json={"revision": revision, "member_user_id": member_user_id},
        )

    def opt_in(user_id: int, revision: int):
        return client.put(
            PREFERENCES, headers=auth(user_id), json={"revision": revision, "mode": "ALL"}
        )

    monkeypatch.setattr(get_settings(), "wecom_corp_id", "   ")
    assert bind(2, 0, "Team-01").status_code == 409
    monkeypatch.setattr(get_settings(), "wecom_corp_id", "ww-corp-one")
    assert bind(2, 0, "Team-01").status_code == 200
    assert opt_in(2, 1).status_code == 200
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        assert item.corp_id == "ww-corp-one"
        original_binding = item.binding_id

    monkeypatch.setattr(get_settings(), "wecom_corp_id", " ww-corp-two ")
    expected = {"revision": 2, "member_user_id": None, "mode": "OFF", "enabled": False}
    assert client.get(PREFERENCES, headers=auth(2)).json() == expected
    assert client.get(binding(2), headers=auth(1)).json() == expected
    assert opt_in(2, 2).status_code == 409
    assert bind(3, 0, "team-01").status_code == 200
    assert bind(2, 2, "Team-01").status_code == 409
    assert bind(3, 1, None).status_code == 200
    rebound = bind(2, 2, "Team-01")
    assert rebound.status_code == 200
    assert rebound.json() == {
        "revision": 3,
        "member_user_id": "Team-01",
        "mode": "OFF",
        "enabled": False,
    }
    with sessions() as db:
        item = db.get(WecomPreference, 2)
        assert item.corp_id == "ww-corp-two"
        assert item.binding_id and item.binding_id != original_binding
        assert item.eligible_since is None
    assert opt_in(2, 3).status_code == 200

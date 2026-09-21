from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
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
from app.models.enums import DataScope, UserStatus

MANAGEMENT_PERMISSIONS = {
    "sys.user.view",
    "sys.user.create",
    "sys.user.edit",
    "sys.user.status",
    "sys.user.role.assign",
    "sys.role.view",
    "sys.role.edit",
}

UserApiFixture = tuple[TestClient, Session, dict[str, str], dict[str, int]]


@pytest.fixture
def user_api(tmp_path: Path) -> Iterator[UserApiFixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'user-api.db'}", connect_args={"check_same_thread": False}
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
        admin = User(
            username="administrator",
            display_name="Administrator",
            password_hash="unused",
            email="admin@example.test",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        member = User(
            username="member",
            display_name="Member",
            password_hash="unused",
            email="member@example.test",
            mobile="13800000000",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        administrator_role = Role(
            code="ADMINISTRATOR",
            name="Administrator",
            data_scope=DataScope.ALL,
        )
        self_user_role = Role(code="SELF_USER", name="Self User", data_scope=DataScope.SELF)
        member_role = Role(code="MEMBER", name="Member", data_scope=DataScope.SELF)
        permissions = [Permission(code=code, name=code) for code in sorted(MANAGEMENT_PERMISSIONS)]
        session.add_all(
            [admin, member, administrator_role, self_user_role, member_role, *permissions]
        )
        session.flush()
        session.add_all(
            [
                UserRole(user_id=admin.id, role_id=administrator_role.id),
                UserRole(user_id=member.id, role_id=self_user_role.id),
                UserRole(user_id=member.id, role_id=member_role.id),
            ]
        )
        for permission in permissions:
            session.add(RolePermission(role_id=administrator_role.id, permission_id=permission.id))
        # Reuse the catalog permissions for this self-scoped test role.
        admin_edit = next(item for item in permissions if item.code == "sys.user.edit")
        session.add_all(
            [
                RolePermission(
                    role_id=self_user_role.id,
                    permission_id=next(
                        item.id for item in permissions if item.code == "sys.user.view"
                    ),
                ),
                RolePermission(role_id=self_user_role.id, permission_id=admin_edit.id),
            ]
        )
        session.commit()

        app.dependency_overrides[get_db] = lambda: session
        headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
        ids = {
            "admin": admin.id,
            "member": member.id,
            "administrator_role": administrator_role.id,
            "self_user_role": self_user_role.id,
            "member_role": member_role.id,
        }
        with TestClient(app) as client:
            yield client, session, headers, ids
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def test_user_management_returns_roles_and_audits_changes(user_api):
    client, session, headers, ids = user_api

    listed = client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert listed.json()["items"][0]["role_ids"]
    assert "password_hash" not in listed.text

    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "new-user",
            "display_name": "New User",
            "password": "not-a-real-password",
            "email": "new@example.test",
            "mobile": "13900000000",
            "role_ids": [ids["member_role"]],
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["role_ids"] == [ids["member_role"]]
    assert created_body["revision"] == 1
    assert "password" not in created_body

    patched = client.patch(
        f"/api/v1/users/{created_body['id']}",
        headers=headers,
        json={"display_name": "Updated User", "revision": created_body["revision"]},
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == 2

    roles_updated = client.put(
        f"/api/v1/users/{created_body['id']}/roles",
        headers=headers,
        json={"role_ids": [ids["self_user_role"]], "revision": patched.json()["revision"]},
    )
    assert roles_updated.status_code == 200
    assert roles_updated.json()["role_ids"] == [ids["self_user_role"]]
    assert roles_updated.json()["revision"] == 3

    audit_actions = set(
        session.scalars(
            select(OperationLog.action).where(OperationLog.entity_id == created_body["id"])
        ).all()
    )
    assert {"CREATE", "UPDATE", "ROLES_UPDATE"}.issubset(audit_actions)


def test_user_role_assignment_uses_revision_and_validates_roles(user_api):
    client, _session, headers, ids = user_api

    updated = client.put(
        f"/api/v1/users/{ids['member']}/roles",
        headers=headers,
        json={"role_ids": [ids["member_role"]], "revision": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    stale = client.put(
        f"/api/v1/users/{ids['member']}/roles",
        headers=headers,
        json={"role_ids": [ids["self_user_role"]], "revision": 1},
    )
    assert stale.status_code == 409

    unknown_role = client.put(
        f"/api/v1/users/{ids['member']}/roles",
        headers=headers,
        json={"role_ids": [999], "revision": 2},
    )
    assert unknown_role.status_code == 422


def test_self_scope_cannot_read_or_edit_other_user_account_data(user_api):
    client, _session, _headers, ids = user_api
    self_headers = {"Authorization": f"Bearer {create_access_token(ids['member'])}"}

    listed = client.get("/api/v1/users", headers=self_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert [item["id"] for item in listed.json()["items"]] == [ids["member"]]
    assert listed.json()["items"][0]["email"] == "member@example.test"

    other = client.get(f"/api/v1/users/{ids['admin']}", headers=self_headers)
    assert other.status_code == 403
    assert "admin@example.test" not in other.text

    other_update = client.patch(
        f"/api/v1/users/{ids['admin']}",
        headers=self_headers,
        json={"display_name": "Nope", "revision": 1},
    )
    assert other_update.status_code == 403


def test_disabled_user_status_update_revokes_sessions_and_is_audited(user_api):
    client, session, headers, ids = user_api
    session.add(
        RefreshSession(
            id="a" * 32,
            user_id=ids["member"],
            token_jti="b" * 32,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    session.commit()

    response = client.patch(
        f"/api/v1/users/{ids['member']}/status",
        headers=headers,
        json={"status": "DISABLED", "revision": 1},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    session.expire_all()
    refresh_session = session.get(RefreshSession, "a" * 32)
    assert refresh_session is not None
    assert refresh_session.revoked_at is not None
    assert refresh_session.revoked_reason == "USER_DISABLED"
    status_audit = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_id == ids["member"],
            OperationLog.action == "STATUS_CHANGE",
        )
    )
    assert status_audit is not None
    assert status_audit.after_data["revoked_session_count"] == 1


def test_openapi_exposes_user_role_assignment_and_safe_response_contract():
    spec_path = Path(__file__).resolve().parents[2] / "spec" / "openapi-v1.5.yaml"
    document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]

    assert schemas["User"]["required"] == [
        "id",
        "username",
        "display_name",
        "status",
        "revision",
        "role_ids",
    ]
    assert "password_hash" not in schemas["User"]["properties"]
    assert schemas["UserPage"]["required"] == ["items", "page", "page_size", "total"]
    assert document["paths"]["/users/{user_id}"]["patch"]["requestBody"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/UserUpdate"}
    assert document["paths"]["/users/{user_id}/roles"]["put"]["requestBody"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/UserRoleUpdate"}

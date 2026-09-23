from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
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
from app.repositories.user_repository import UserRepository

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
        manager = User(
            username="manager",
            display_name="Manager",
            password_hash="unused",
            email="manager@example.test",
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
        super_admin_role = Role(
            code="SUPER_ADMIN",
            name="Super Administrator",
            data_scope=DataScope.ALL,
            is_system=True,
            enabled=True,
        )
        administrator_role = Role(
            code="ADMINISTRATOR",
            name="Administrator",
            data_scope=DataScope.ALL,
        )
        self_user_role = Role(code="SELF_USER", name="Self User", data_scope=DataScope.SELF)
        member_role = Role(code="MEMBER", name="Member", data_scope=DataScope.SELF)
        disabled_role = Role(
            code="DISABLED_ROLE",
            name="Disabled Role",
            data_scope=DataScope.SELF,
            enabled=False,
        )
        permissions = [Permission(code=code, name=code) for code in sorted(MANAGEMENT_PERMISSIONS)]
        session.add_all(
            [
                admin,
                manager,
                member,
                super_admin_role,
                administrator_role,
                self_user_role,
                member_role,
                disabled_role,
                *permissions,
            ]
        )
        session.flush()
        session.add_all(
            [
                UserRole(user_id=admin.id, role_id=super_admin_role.id),
                UserRole(user_id=manager.id, role_id=administrator_role.id),
                UserRole(user_id=member.id, role_id=self_user_role.id),
                UserRole(user_id=member.id, role_id=member_role.id),
            ]
        )
        for permission in permissions:
            session.add_all(
                [
                    RolePermission(role_id=super_admin_role.id, permission_id=permission.id),
                    RolePermission(role_id=administrator_role.id, permission_id=permission.id),
                ]
            )
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
            "manager": manager.id,
            "super_admin_role": super_admin_role.id,
            "member": member.id,
            "administrator_role": administrator_role.id,
            "self_user_role": self_user_role.id,
            "member_role": member_role.id,
            "disabled_role": disabled_role.id,
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
    assert listed.json()["total"] == 3
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
    client, session, _headers, ids = user_api
    headers = {"Authorization": f"Bearer {create_access_token(ids['manager'])}"}

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

    disabled_role = client.put(
        f"/api/v1/users/{ids['member']}/roles",
        headers=headers,
        json={"role_ids": [ids["disabled_role"]], "revision": 2},
    )
    assert disabled_role.status_code == 422

    session.expire_all()
    member = session.get(User, ids["member"])
    assert member is not None
    assert member.revision == 2
    assert set(UserRepository(session).role_ids(member.id)) == {ids["member_role"]}
    audit = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_id == member.id,
            OperationLog.action == "ROLES_UPDATE",
        )
    )
    assert audit is not None
    assert audit.before_data["role_ids"] == sorted([ids["self_user_role"], ids["member_role"]])
    assert audit.after_data["role_ids"] == [ids["member_role"]]


def test_non_super_admin_cannot_grant_super_admin_to_self_or_others(user_api):
    client, session, _headers, ids = user_api
    manager_headers = {"Authorization": f"Bearer {create_access_token(ids['manager'])}"}

    grant_other = client.put(
        f"/api/v1/users/{ids['member']}/roles",
        headers=manager_headers,
        json={
            "role_ids": [ids["member_role"], ids["super_admin_role"]],
            "revision": 1,
        },
    )
    assert grant_other.status_code == 403

    grant_self = client.put(
        f"/api/v1/users/{ids['manager']}/roles",
        headers=manager_headers,
        json={
            "role_ids": [ids["administrator_role"], ids["super_admin_role"]],
            "revision": 1,
        },
    )
    assert grant_self.status_code == 403

    session.expire_all()
    assert session.get(User, ids["member"]).revision == 1
    assert session.get(User, ids["manager"]).revision == 1
    assert ids["super_admin_role"] not in UserRepository(session).role_ids(ids["member"])
    assert ids["super_admin_role"] not in UserRepository(session).role_ids(ids["manager"])


def test_non_super_admin_cannot_revoke_super_admin(user_api):
    client, session, _headers, ids = user_api
    manager_headers = {"Authorization": f"Bearer {create_access_token(ids['manager'])}"}

    response = client.put(
        f"/api/v1/users/{ids['admin']}/roles",
        headers=manager_headers,
        json={"role_ids": [], "revision": 1},
    )

    assert response.status_code == 403
    session.expire_all()
    assert session.get(User, ids["admin"]).revision == 1
    assert UserRepository(session).role_ids(ids["admin"]) == [ids["super_admin_role"]]


def test_super_admin_can_grant_and_revoke_second_super_admin(user_api):
    client, session, headers, ids = user_api

    granted = client.put(
        f"/api/v1/users/{ids['manager']}/roles",
        headers=headers,
        json={
            "role_ids": [ids["administrator_role"], ids["super_admin_role"]],
            "revision": 1,
        },
    )
    assert granted.status_code == 200
    assert granted.json()["revision"] == 2
    assert ids["super_admin_role"] in granted.json()["role_ids"]

    revoked = client.put(
        f"/api/v1/users/{ids['manager']}/roles",
        headers=headers,
        json={"role_ids": [ids["administrator_role"]], "revision": 2},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revision"] == 3
    assert ids["super_admin_role"] not in revoked.json()["role_ids"]
    session.expire_all()
    assert UserRepository(session).effective_super_admin_count(ids["super_admin_role"]) == 1


def test_last_effective_super_admin_role_cannot_be_removed(user_api):
    client, session, headers, ids = user_api

    response = client.put(
        f"/api/v1/users/{ids['admin']}/roles",
        headers=headers,
        json={"role_ids": [], "revision": 1},
    )

    assert response.status_code == 409
    assert response.json()["message"] == "至少必须保留一个有效的超级管理员"
    session.expire_all()
    assert session.get(User, ids["admin"]).revision == 1
    assert UserRepository(session).role_ids(ids["admin"]) == [ids["super_admin_role"]]


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
    assert status_audit.before_data == {"status": "ACTIVE"}
    assert status_audit.after_data["status"] == "DISABLED"
    assert status_audit.after_data["revoked_session_count"] == 1


def test_non_super_admin_cannot_change_super_admin_status(user_api):
    client, session, _headers, ids = user_api
    manager_headers = {"Authorization": f"Bearer {create_access_token(ids['manager'])}"}

    response = client.patch(
        f"/api/v1/users/{ids['admin']}/status",
        headers=manager_headers,
        json={"status": "DISABLED", "revision": 1},
    )

    assert response.status_code == 403
    session.expire_all()
    admin = session.get(User, ids["admin"])
    assert admin is not None
    assert admin.status is UserStatus.ACTIVE
    assert admin.revision == 1


@pytest.mark.parametrize("status", ["DISABLED", "LOCKED"])
def test_last_effective_super_admin_cannot_be_made_inactive(user_api, status):
    client, session, headers, ids = user_api

    response = client.patch(
        f"/api/v1/users/{ids['admin']}/status",
        headers=headers,
        json={"status": status, "revision": 1},
    )

    assert response.status_code == 409
    assert response.json()["message"] == "至少必须保留一个有效的超级管理员"
    session.expire_all()
    admin = session.get(User, ids["admin"])
    assert admin is not None
    assert admin.status is UserStatus.ACTIVE
    assert admin.revision == 1


def test_one_of_two_effective_super_admins_can_be_disabled(user_api):
    client, session, headers, ids = user_api

    granted = client.put(
        f"/api/v1/users/{ids['manager']}/roles",
        headers=headers,
        json={
            "role_ids": [ids["administrator_role"], ids["super_admin_role"]],
            "revision": 1,
        },
    )
    assert granted.status_code == 200

    disabled = client.patch(
        f"/api/v1/users/{ids['manager']}/status",
        headers=headers,
        json={"status": "DISABLED", "revision": granted.json()["revision"]},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    assert disabled.json()["revision"] == 3
    session.expire_all()
    assert UserRepository(session).effective_super_admin_count(ids["super_admin_role"]) == 1


def test_non_super_admin_can_create_normal_user_but_not_super_admin(user_api):
    client, session, _headers, ids = user_api
    manager_headers = {"Authorization": f"Bearer {create_access_token(ids['manager'])}"}

    normal = client.post(
        "/api/v1/users",
        headers=manager_headers,
        json={
            "username": "normal-by-manager",
            "display_name": "Normal User",
            "password": "not-a-real-password",
            "role_ids": [ids["member_role"]],
        },
    )
    assert normal.status_code == 200
    assert normal.json()["role_ids"] == [ids["member_role"]]

    elevated = client.post(
        "/api/v1/users",
        headers=manager_headers,
        json={
            "username": "blocked-super-admin",
            "display_name": "Blocked Super Admin",
            "password": "not-a-real-password",
            "role_ids": [ids["super_admin_role"]],
        },
    )
    assert elevated.status_code == 403
    session.expire_all()
    assert UserRepository(session).by_username("blocked-super-admin") is None


def test_super_admin_can_create_another_super_admin(user_api):
    client, session, headers, ids = user_api

    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "second-super-admin",
            "display_name": "Second Super Admin",
            "password": "not-a-real-password",
            "role_ids": [ids["super_admin_role"]],
        },
    )

    assert response.status_code == 200
    assert response.json()["role_ids"] == [ids["super_admin_role"]]
    session.expire_all()
    assert UserRepository(session).effective_super_admin_count(ids["super_admin_role"]) == 2


def test_super_admin_lock_statement_uses_postgresql_for_update():
    compiled = str(
        UserRepository.super_admin_lock_statement().compile(dialect=postgresql_dialect())
    ).upper()

    assert "FOR UPDATE" in compiled
    assert "SYS_ROLE.CODE" in compiled
    assert "SYS_ROLE.IS_SYSTEM" in compiled


def test_openapi_exposes_user_role_assignment_and_safe_response_contract():
    spec_dir = Path(__file__).resolve().parents[2] / "spec"
    for filename in ("openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"):
        document = yaml.safe_load((spec_dir / filename).read_text(encoding="utf-8"))
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
        roles_operation = document["paths"]["/users/{user_id}/roles"]["put"]
        assert roles_operation["requestBody"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/UserRoleUpdate"
        }
        assert "SUPER_ADMIN" in roles_operation["responses"]["403"]["description"]
        assert "最后一个" in roles_operation["responses"]["409"]["description"]
        status_operation = document["paths"]["/users/{user_id}/status"]["patch"]
        assert "SUPER_ADMIN" in status_operation["responses"]["403"]["description"]
        assert "最后一个" in status_operation["responses"]["409"]["description"]
        create_operation = document["paths"]["/users"]["post"]
        assert "SUPER_ADMIN" in create_operation["responses"]["403"]["description"]

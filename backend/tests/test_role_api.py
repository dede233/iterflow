from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.cli.seed import PERMISSIONS as SEEDED_PERMISSIONS
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import OperationLog, Permission, Role, RolePermission, User, UserRole
from app.models.enums import DataScope, UserStatus
from app.services.permission_catalog import PermissionCatalog

RoleApiFixture = tuple[TestClient, Session, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def role_api(tmp_path: Path) -> Iterator[RoleApiFixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'role-api.db'}", connect_args={"check_same_thread": False}
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        OperationLog.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission, OperationLog):
        counter = iter(range(1, 1_000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        permissions = {
            code: Permission(code=code, name=name) for code, name in SEEDED_PERMISSIONS.items()
        }
        manager_role = Role(
            code="ROLE_MANAGER", name="角色管理员", data_scope=DataScope.ALL, is_system=True
        )
        viewer_role = Role(
            code="ROLE_VIEWER", name="角色查看者", data_scope=DataScope.ALL, is_system=True
        )
        system_role = Role(
            code="SUPER_ADMIN", name="超级管理员", data_scope=DataScope.ALL, is_system=True
        )
        assigned_role = Role(
            code="ASSIGNED_ROLE", name="已分配角色", data_scope=DataScope.SELF, is_system=False
        )
        session.add_all(
            [manager_role, viewer_role, system_role, assigned_role, *permissions.values()]
        )
        session.flush()
        session.add_all(
            [
                RolePermission(
                    role_id=manager_role.id, permission_id=permissions["sys.role.view"].id
                ),
                RolePermission(
                    role_id=manager_role.id, permission_id=permissions["sys.role.manage"].id
                ),
                RolePermission(
                    role_id=viewer_role.id, permission_id=permissions["sys.role.view"].id
                ),
                RolePermission(
                    role_id=system_role.id, permission_id=permissions["rd.feedback.view"].id
                ),
            ]
        )

        def user(username: str) -> User:
            return User(
                username=username,
                display_name=username.title(),
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )

        manager, viewer, assigned_user = user("manager"), user("viewer"), user("assigned")
        session.add_all([manager, viewer, assigned_user])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=manager.id, role_id=manager_role.id),
                UserRole(user_id=viewer.id, role_id=viewer_role.id),
                UserRole(user_id=assigned_user.id, role_id=assigned_role.id),
            ]
        )
        session.commit()

        ids = {
            "manager": manager.id,
            "viewer": viewer.id,
            "system_role": system_role.id,
            "assigned_role": assigned_role.id,
            "feedback_permission": permissions["rd.feedback.view"].id,
        }
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(ids[name])}"}
            for name in ("manager", "viewer")
        }
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, session, headers, ids
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def test_role_crud_and_audit_before_after(role_api: RoleApiFixture):
    client, session, headers, ids = role_api

    created = client.post(
        "/api/v1/roles",
        headers=headers["manager"],
        json={
            "code": "CUSTOM_ROLE",
            "name": "自定义角色",
            "data_scope": "SELF",
            "permission_ids": [ids["feedback_permission"]],
        },
    )
    assert created.status_code == 200, created.text
    role = created.json()
    assert role["is_system"] is False
    assert role["permission_ids"] == [ids["feedback_permission"]]

    listed = client.get("/api/v1/roles", headers=headers["manager"])
    assert listed.status_code == 200
    assert any(item["id"] == role["id"] for item in listed.json())

    detail = client.get(f"/api/v1/roles/{role['id']}", headers=headers["manager"])
    assert detail.status_code == 200
    assert detail.json()["code"] == "CUSTOM_ROLE"

    updated = client.patch(
        f"/api/v1/roles/{role['id']}",
        headers=headers["manager"],
        json={
            "code": "CUSTOM_ROLE_UPDATED",
            "name": "更新后的角色",
            "data_scope": "ALL",
            "enabled": False,
            "revision": role["revision"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert updated.json()["code"] == "CUSTOM_ROLE_UPDATED"
    assert updated.json()["data_scope"] == "ALL"
    assert updated.json()["enabled"] is False

    permissions_updated = client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=headers["manager"],
        json={"permission_ids": [], "revision": updated.json()["revision"]},
    )
    assert permissions_updated.status_code == 200
    assert permissions_updated.json()["permission_ids"] == []
    assert permissions_updated.json()["revision"] == 3

    stale_update = client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=headers["manager"],
        json={
            "permission_ids": [ids["feedback_permission"]],
            "revision": updated.json()["revision"],
        },
    )
    assert stale_update.status_code == 409

    unknown_permission = client.put(
        f"/api/v1/roles/{role['id']}/permissions",
        headers=headers["manager"],
        json={"permission_ids": [999_999], "revision": permissions_updated.json()["revision"]},
    )
    assert unknown_permission.status_code == 422

    create_audit = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_id == role["id"], OperationLog.action == "ROLE_CREATE"
        )
    )
    update_audit = session.scalar(
        select(OperationLog)
        .where(OperationLog.entity_id == role["id"], OperationLog.action == "ROLE_UPDATE")
        .order_by(OperationLog.id)
    )
    permission_audit = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_id == role["id"],
            OperationLog.action == "ROLE_PERMISSION_UPDATE",
        )
    )
    assert create_audit is not None
    assert create_audit.after_data["code"] == "CUSTOM_ROLE"
    assert update_audit is not None
    assert update_audit.before_data["name"] == "自定义角色"
    assert update_audit.after_data["name"] == "更新后的角色"
    assert permission_audit is not None
    assert permission_audit.before_data["permission_ids"] == [ids["feedback_permission"]]
    assert permission_audit.after_data["permission_ids"] == []

    deleted = client.delete(f"/api/v1/roles/{role['id']}", headers=headers["manager"])
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": role["id"], "deleted": True}
    assert client.get(f"/api/v1/roles/{role['id']}", headers=headers["manager"]).status_code == 404
    delete_audit = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_id == role["id"], OperationLog.action == "ROLE_DELETE"
        )
    )
    assert delete_audit is not None
    assert delete_audit.before_data["code"] == "CUSTOM_ROLE_UPDATED"
    assert delete_audit.after_data is None


def test_role_write_requires_manage_permission(role_api: RoleApiFixture):
    client, _session, headers, _ids = role_api

    assert client.get("/api/v1/roles", headers=headers["viewer"]).status_code == 200
    assert (
        client.post(
            "/api/v1/roles",
            headers=headers["viewer"],
            json={"code": "NOPE", "name": "无权创建", "data_scope": "SELF"},
        ).status_code
        == 403
    )


def test_permission_catalog_returns_every_permission_as_read_only_metadata(
    role_api: RoleApiFixture,
):
    client, _session, headers, _ids = role_api

    response = client.get("/api/v1/roles/permissions", headers=headers["manager"])
    assert response.status_code == 200
    catalog = response.json()
    assert {item["code"] for item in catalog} == set(SEEDED_PERMISSIONS)
    assert all(item["group"] != "Other / 其他" for item in catalog)

    by_code = {item["code"]: item for item in catalog}
    assert by_code["dashboard.view"]["group"] == "Dashboard / 首页"
    assert by_code["rd.version.publish"]["group"] == "Version / 版本"
    assert by_code["sys.user.role.assign"]["group"] == "User / 用户管理"
    assert by_code["sys.file.download"]["group"] == "File / 文件"
    assert {
        item["code"] for item in catalog if item["sensitive"]
    } == PermissionCatalog.SENSITIVE_CODES

    dynamic_path = app.openapi()["paths"]["/api/v1/roles/permissions"]
    assert set(dynamic_path) == {"get"}


def test_permission_catalog_keeps_unknown_codes_visible():
    assert PermissionCatalog.group_for("integration.webhook.run").label == "Other / 其他"


def test_system_role_and_assigned_role_cannot_be_deleted(role_api: RoleApiFixture):
    client, _session, headers, ids = role_api

    system_delete = client.delete(f"/api/v1/roles/{ids['system_role']}", headers=headers["manager"])
    assert system_delete.status_code == 409

    assigned_delete = client.delete(
        f"/api/v1/roles/{ids['assigned_role']}", headers=headers["manager"]
    )
    assert assigned_delete.status_code == 409
    assert assigned_delete.json()["data"]["user_count"] == 1


def test_system_role_is_read_only_and_permissions_cannot_be_cleared(
    role_api: RoleApiFixture,
):
    client, _session, headers, ids = role_api
    role_url = f"/api/v1/roles/{ids['system_role']}"

    original = client.get(role_url, headers=headers["manager"])
    assert original.status_code == 200
    original_role = original.json()
    assert original_role["code"] == "SUPER_ADMIN"
    assert original_role["is_system"] is True
    assert original_role["permission_ids"] == [ids["feedback_permission"]]

    patched = client.patch(
        role_url,
        headers=headers["manager"],
        json={
            "code": "SUPER_ADMIN_RENAMED",
            "data_scope": "SELF",
            "enabled": False,
            "revision": original_role["revision"],
        },
    )
    assert patched.status_code == 409

    permissions_updated = client.put(
        f"{role_url}/permissions",
        headers=headers["manager"],
        json={"permission_ids": [], "revision": original_role["revision"]},
    )
    assert permissions_updated.status_code == 409

    unchanged = client.get(role_url, headers=headers["manager"])
    assert unchanged.status_code == 200
    assert unchanged.json()["code"] == "SUPER_ADMIN"
    assert unchanged.json()["data_scope"] == "ALL"
    assert unchanged.json()["enabled"] is True
    assert unchanged.json()["revision"] == original_role["revision"]
    assert unchanged.json()["permission_ids"] == [ids["feedback_permission"]]


def test_static_openapi_role_management_contract():
    spec_dir = Path(__file__).resolve().parents[2] / "spec"
    for filename in ("openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"):
        document = yaml.safe_load((spec_dir / filename).read_text(encoding="utf-8"))
        role_schema = document["components"]["schemas"]["Role"]
        permission_schema = document["components"]["schemas"]["Permission"]
        assert "is_system" in role_schema["required"]
        assert role_schema["properties"]["is_system"] == {"type": "boolean"}
        assert {"group", "sensitive"} <= set(permission_schema["required"])
        assert permission_schema["properties"]["group"]["type"] == "string"
        assert permission_schema["properties"]["sensitive"]["type"] == "boolean"
        assert set(document["paths"]["/roles/permissions"]) == {"get"}
        assert "get" in document["paths"]["/roles/{role_id}"]
        assert "delete" in document["paths"]["/roles/{role_id}"]
        assert (
            "系统角色"
            in document["paths"]["/roles/{role_id}"]["patch"]["responses"]["409"]["description"]
        )
        assert (
            "系统角色"
            in document["paths"]["/roles/{role_id}/permissions"]["put"]["responses"]["409"][
                "description"
            ]
        )
        assert (
            "系统角色"
            in document["paths"]["/roles/{role_id}"]["delete"]["responses"]["409"]["description"]
        )

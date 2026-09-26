from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import DataScope, UserStatus


@pytest.fixture
def catalog_api(tmp_path: Path) -> Iterator[tuple[TestClient, Session, dict[str, dict[str, str]]]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'catalog.db'}", connect_args={"check_same_thread": False}
    )
    models = (
        User,
        Role,
        Permission,
        UserRole,
        RolePermission,
        BusinessSystem,
        BusinessModule,
        OperationLog,
    )
    for model in models:
        model.__table__.create(engine)

    listeners = []
    for model in (User, Role, Permission, BusinessSystem, BusinessModule, OperationLog):
        counter = iter(range(1, 1000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        view = Permission(code="sys.system.view", name="系统模块查看")
        manage = Permission(code="sys.system.manage", name="系统模块管理")
        audit_view = Permission(code="sys.audit.view", name="审计查看")
        roles = {
            "manager": Role(code="CATALOG_MANAGER", name="管理员", data_scope=DataScope.ALL),
            "viewer": Role(code="CATALOG_VIEWER", name="查看者", data_scope=DataScope.ALL),
            "self": Role(code="CATALOG_SELF", name="仅本人管理员", data_scope=DataScope.SELF),
            "outsider": Role(code="CATALOG_OUTSIDER", name="无权限", data_scope=DataScope.ALL),
        }
        session.add_all([view, manage, audit_view, *roles.values()])
        session.flush()
        session.add_all(
            [
                RolePermission(role_id=roles["manager"].id, permission_id=manage.id),
                RolePermission(role_id=roles["manager"].id, permission_id=view.id),
                RolePermission(role_id=roles["manager"].id, permission_id=audit_view.id),
                RolePermission(role_id=roles["viewer"].id, permission_id=view.id),
                RolePermission(role_id=roles["self"].id, permission_id=manage.id),
                RolePermission(role_id=roles["self"].id, permission_id=view.id),
                RolePermission(role_id=roles["self"].id, permission_id=audit_view.id),
            ]
        )
        users = {}
        for name, role in roles.items():
            user = User(
                username=name,
                display_name=name,
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            session.add(user)
            session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
            users[name] = user
        session.commit()
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(user.id)}"}
            for name, user in users.items()
        }
        app.dependency_overrides[get_db] = lambda: session
        try:
            with TestClient(app) as client:
                yield client, session, headers
        finally:
            app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def test_manage_systems_modules_revision_and_audit(catalog_api):
    client, session, headers = catalog_api
    admin = headers["manager"]

    created = client.post(
        "/api/v1/systems",
        headers=admin,
        json={"code": "ITERFLOW", "name": "迭程", "sort_order": 2},
    )
    assert created.status_code == 201, created.text
    system = created.json()
    assert system["revision"] == 1
    assert system["enabled"] is True

    module_response = client.post(
        f"/api/v1/systems/{system['id']}/modules",
        headers=admin,
        json={"code": "FEEDBACK", "name": "反馈中心"},
    )
    assert module_response.status_code == 201, module_response.text
    module = module_response.json()
    assert module["system_id"] == system["id"]

    enabled = client.get("/api/v1/systems", headers=headers["viewer"])
    assert enabled.status_code == 200
    assert [item["code"] for item in enabled.json()["systems"]] == ["ITERFLOW"]
    assert [item["code"] for item in enabled.json()["modules"]] == ["FEEDBACK"]

    renamed = client.patch(
        f"/api/v1/systems/modules/{module['id']}",
        headers=admin,
        json={"name": "反馈与建议", "revision": module["revision"]},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["revision"] == 2
    assert renamed.json()["name"] == "反馈与建议"
    stale_module = client.patch(
        f"/api/v1/systems/modules/{module['id']}",
        headers=admin,
        json={"name": "覆盖保存", "revision": module["revision"]},
    )
    assert stale_module.status_code == 409
    assert stale_module.json()["data"]["current_revision"] == 2

    disabled = client.patch(
        f"/api/v1/systems/{system['id']}",
        headers=admin,
        json={"enabled": False, "revision": system["revision"]},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["revision"] == 2
    assert client.get("/api/v1/systems", headers=headers["viewer"]).json() == {
        "systems": [],
        "modules": [],
    }
    managed = client.get("/api/v1/systems/manage", headers=admin)
    assert managed.status_code == 200
    assert managed.json()["systems"][0]["enabled"] is False
    assert managed.json()["modules"][0]["name"] == "反馈与建议"
    assert session.get(BusinessSystem, system["id"]) is not None
    assert session.get(BusinessModule, module["id"]) is not None

    stale_system = client.patch(
        f"/api/v1/systems/{system['id']}",
        headers=admin,
        json={"name": "覆盖保存", "revision": system["revision"]},
    )
    assert stale_system.status_code == 409
    assert stale_system.json()["data"]["current_revision"] == 2

    logs = session.scalars(select(OperationLog).order_by(OperationLog.id)).all()
    assert [log.action for log in logs] == [
        "SYSTEM_CREATE",
        "MODULE_CREATE",
        "MODULE_UPDATE",
        "SYSTEM_UPDATE",
    ]
    assert logs[2].before_data["name"] == "反馈中心"
    assert logs[2].after_data["name"] == "反馈与建议"
    assert all(log.operator_id is not None for log in logs)

    audit_page = client.get("/api/v1/audits", headers=admin)
    assert audit_page.status_code == 200, audit_page.text
    assert audit_page.json()["total"] == 4
    assert {item["entity_type"] for item in audit_page.json()["items"]} == {
        "BUSINESS_SYSTEM",
        "BUSINESS_MODULE",
    }
    assert client.get("/api/v1/audits", headers=headers["self"]).json()["total"] == 0


def test_catalog_permissions_duplicates_and_validation(catalog_api):
    client, _session, headers = catalog_api
    assert client.get("/api/v1/systems").status_code == 401
    assert client.get("/api/v1/systems/manage", headers=headers["viewer"]).status_code == 403
    assert client.post("/api/v1/systems", headers=headers["viewer"], json={}).status_code == 403
    assert client.get("/api/v1/systems/manage", headers=headers["self"]).status_code == 403
    assert (
        client.post(
            "/api/v1/systems",
            headers=headers["self"],
            json={"code": "X", "name": "X"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/systems", headers=headers["outsider"]).status_code == 403

    admin = headers["manager"]
    system = client.post(
        "/api/v1/systems",
        headers=admin,
        json={"code": "APP", "name": "应用"},
    ).json()
    duplicate = client.post(
        "/api/v1/systems",
        headers=admin,
        json={"code": "APP", "name": "重复"},
    )
    assert duplicate.status_code == 409
    assert (
        client.post(
            f"/api/v1/systems/{system['id']}/modules",
            headers=admin,
            json={"code": "WEB", "name": "Web"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/systems/{system['id']}/modules",
            headers=admin,
            json={"code": "WEB", "name": "重复"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/systems/999/modules",
            headers=admin,
            json={"code": "WEB", "name": "不存在"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/systems/{system['id']}",
            headers=admin,
            json={"revision": system["revision"]},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/systems/{system['id']}",
            headers=admin,
            json={"name": None, "revision": system["revision"]},
        ).status_code
        == 422
    )

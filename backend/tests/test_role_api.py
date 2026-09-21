from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

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
)
from app.models.enums import DataScope


@pytest.fixture
def role_api(tmp_path: Path) -> Iterator[tuple[TestClient, Session, dict[str, str]]]:
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
        counter = iter(range(1, 1000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        user = User(
            username="role-reviewer",
            display_name="Role Reviewer",
            password_hash="unused",
            must_change_password=False,
        )
        authorizer = Role(code="ROLE_AUTHORIZER", name="角色测试授权", data_scope=DataScope.ALL)
        view_permission = Permission(code="sys.role.view", name="角色查看")
        edit_permission = Permission(code="sys.role.edit", name="角色编辑")
        session.add_all([user, authorizer, view_permission, edit_permission])
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=authorizer.id))
        session.add_all(
            [
                RolePermission(role_id=authorizer.id, permission_id=view_permission.id),
                RolePermission(role_id=authorizer.id, permission_id=edit_permission.id),
            ]
        )
        session.commit()

        app.dependency_overrides[get_db] = lambda: session
        headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
        with TestClient(app) as client:
            yield client, session, headers
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def test_role_list_create_and_patch_responses_include_revision(role_api):
    client, _session, headers = role_api

    created = client.post(
        "/api/v1/roles",
        headers=headers,
        json={"code": "MEMBER", "name": "普通成员", "data_scope": "SELF"},
    )
    assert created.status_code == 200
    assert created.json()["revision"] == 1

    listed = client.get("/api/v1/roles", headers=headers)
    assert listed.status_code == 200
    assert all("revision" in role for role in listed.json())

    updated = client.patch(
        f"/api/v1/roles/{created.json()['id']}",
        headers=headers,
        json={"name": "普通成员-更新", "revision": created.json()["revision"]},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2


def test_role_permission_update_returns_404_for_missing_role(role_api):
    client, _session, headers = role_api

    response = client.put(
        "/api/v1/roles/999/permissions",
        headers=headers,
        json={"permission_ids": [], "revision": 1},
    )

    assert response.status_code == 404
    assert response.json()["code"] == 40401


def test_static_openapi_role_contract_exposes_revision_and_role_responses():
    spec_path = Path(__file__).resolve().parents[2] / "spec" / "openapi-v1.5.yaml"
    document = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    role_schema = document["components"]["schemas"]["Role"]

    assert "revision" in role_schema["required"]
    assert "permission_ids" in role_schema["required"]
    assert role_schema["properties"]["revision"] == {"type": "integer", "minimum": 1}
    assert role_schema["properties"]["permission_ids"] == {
        "type": "array",
        "items": {"type": "integer"},
    }
    assert document["paths"]["/roles"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["items"] == {"$ref": "#/components/schemas/Role"}
    assert document["paths"]["/roles"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/Role"}
    assert document["paths"]["/roles/permissions"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["items"] == {"$ref": "#/components/schemas/Permission"}

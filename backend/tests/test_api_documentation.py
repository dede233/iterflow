import json
import os
import subprocess
import sys
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.api_documentation import schema_labels
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import OperationLog, Permission, Role, RolePermission, User, UserRole
from app.models.enums import DataScope, UserStatus
from scripts.build_api_documentation import documentation_labels


class PrivateHeaders(dict):
    def __repr__(self) -> str:
        return "<redacted authorization headers>"


@pytest.fixture
def docs_api(tmp_path: Path) -> Iterator[tuple[TestClient, Session, User, dict[str, str]]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'docs.db'}", connect_args={"check_same_thread": False}
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
            username="docs-user",
            display_name="文档用户",
            password_hash="not-used",
            must_change_password=False,
        )
        session.add(user)
        session.commit()
        headers = PrivateHeaders(Authorization=f"Bearer {create_access_token(user.id)}")
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, session, user, headers
        app.dependency_overrides.clear()
    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def assign_role(session: Session, user: User, code: str, *, system: bool = True) -> Role:
    role = Role(code=code, name=code, enabled=True, is_system=system, data_scope=DataScope.SELF)
    session.add(role)
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.commit()
    return role


def test_anonymous_cannot_read_documentation(docs_api):
    client, _, _, _ = docs_api
    response = client.get("/api/v1/docs/openapi")
    assert response.status_code == 401
    assert "paths" not in response.json()


@pytest.mark.parametrize(
    "code,allowed",
    [
        ("SUPER_ADMIN", True),
        ("DEVELOPMENT_LEAD", True),
        ("MEMBER", False),
        ("PRODUCT_MANAGER", False),
        ("TESTER", False),
        ("CUSTOM_ADMIN", False),
    ],
)
def test_exact_enabled_system_roles_control_menu_capability_and_schema(docs_api, code, allowed):
    client, session, user, headers = docs_api
    assign_role(session, user, code)
    assert client.get("/api/v1/auth/me", headers=headers).json()["can_view_api_docs"] is allowed
    response = client.get("/api/v1/docs/openapi", headers=headers)
    assert response.status_code == (200 if allowed else 403)
    if allowed:
        assert response.headers["cache-control"] == "private, no-store"
        assert "Authorization" in response.headers["vary"].split(", ")
        schema = response.json()
        assert schema["info"]["title"] == "迭程 IterFlow 接口文档"
        assert schema["paths"]["/api/v1/auth/login"]["post"]["summary"] == "登录"
        assert "/api/v1/versions/{version_id}/publish" in schema["paths"]
        assert (
            schema["components"]["schemas"]["FeedbackOut"]["properties"]["feedback_no"]["title"]
            == "反馈编号"
        )
        assert (
            schema["components"]["schemas"]["FeedbackPage"]["properties"]["items"]["title"]
            == "数据列表"
        )
        assert (
            schema["components"]["schemas"]["TokenPair"]["properties"]["access_token"]["title"]
            == "访问令牌"
        )
        entry = session.scalar(select(OperationLog).where(OperationLog.action == "VIEW"))
        assert entry is not None and entry.operator_id == user.id
        assert entry.before_data is None and entry.after_data is None
    else:
        assert "paths" not in response.json()


def test_role_revocation_takes_effect_with_the_same_access_token(docs_api):
    client, session, user, headers = docs_api
    role = assign_role(session, user, "DEVELOPMENT_LEAD")
    assert client.get("/api/v1/docs/openapi", headers=headers).status_code == 200
    role.enabled = False
    session.commit()
    assert client.get("/api/v1/docs/openapi", headers=headers).status_code == 403
    assert not client.get("/api/v1/auth/me", headers=headers).json()["can_view_api_docs"]


def test_wildcard_permission_and_custom_role_cannot_bypass_role_gate(docs_api):
    client, session, user, headers = docs_api
    role = assign_role(session, user, "SUPER_ADMIN", system=False)
    permission = Permission(code="*", name="全部权限")
    session.add(permission)
    session.flush()
    session.add(RolePermission(role_id=role.id, permission_id=permission.id))
    session.commit()
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["permission_codes"] == ["*"] and not me["can_view_api_docs"]
    assert client.get("/api/v1/docs/openapi", headers=headers).status_code == 403


@pytest.mark.parametrize(
    "status,must_change,expected",
    [
        (UserStatus.DISABLED, False, 401),
        (UserStatus.ACTIVE, True, 403),
    ],
)
def test_disabled_and_first_login_accounts_cannot_read_schema(
    docs_api, status, must_change, expected
):
    client, session, user, headers = docs_api
    assign_role(session, user, "SUPER_ADMIN")
    user.status = status
    user.must_change_password = must_change
    session.commit()
    assert client.get("/api/v1/docs/openapi", headers=headers).status_code == expected


def test_bundled_chinese_labels_match_the_active_contract():
    root = Path(__file__).resolve().parents[2]
    current = yaml.safe_load((root / "spec/openapi-development.yaml").read_text())
    bundled = json.loads((root / "backend/app/core/api_documentation.json").read_text())
    assert bundled == documentation_labels(current)
    released = yaml.safe_load((root / "spec/openapi-v1.8.1.yaml").read_text())
    current["paths"].pop("/docs/openapi")
    current["components"]["schemas"]["AuthMe"]["properties"].pop("can_view_api_docs")
    current["info"] = released["info"]
    for document in (current, released):
        for schema in document["components"]["schemas"].values():
            remove_schema_annotations(schema)
    assert current == released


def remove_schema_annotations(schema):
    schema.pop("title", None)
    schema.pop("description", None)
    for child in schema.get("properties", {}).values():
        remove_schema_annotations(child)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            remove_schema_annotations(schema[key])
    for key in ("anyOf", "allOf", "oneOf"):
        for child in schema.get(key, []):
            remove_schema_annotations(child)


def test_documented_response_fields_are_chinese_and_keep_runtime_structure(docs_api):
    client, session, user, headers = docs_api
    assign_role(session, user, "SUPER_ADMIN")
    original = deepcopy(app.openapi())
    result = client.get("/api/v1/docs/openapi", headers=headers).json()
    assert app.openapi() == original, "documentation must not modify the cached runtime schema"
    for name, schema in result["components"]["schemas"].items():
        for field in schema.get("properties", {}).values():
            assert any("\u3400" <= char <= "\u9fff" for char in field["title"]), name
        runtime = deepcopy(original["components"]["schemas"][name])
        documented = deepcopy(schema)
        remove_schema_annotations(runtime)
        remove_schema_annotations(documented)
        assert documented == runtime, name
    labels = schema_labels(
        {"type": "object", "properties": {"title": {"type": "string", "title": "标题"}}}
    )
    assert labels == {"properties": {"title": {"title": "标题"}}}


def test_production_cannot_enable_public_swagger_or_schema():
    env = dict(os.environ, APP_ENV="production", ENABLE_API_DOCS="true", ALLOWED_HOSTS="testserver")
    script = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    for path in ('/docs', '/redoc', '/openapi.json'):
        assert client.get(path).status_code == 404, path
    assert client.get('/api/v1/docs/openapi').status_code == 401
"""
    subprocess.run([sys.executable, "-c", script], env=env, check=True)

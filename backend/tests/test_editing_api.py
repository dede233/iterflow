from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    Feedback,
    Permission,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    FeedbackType,
    FeedbackUrgency,
    Priority,
    RequirementSource,
    RequirementStatus,
    UserStatus,
    VersionStatus,
)
from app.services.editing_service import EditingService


@pytest.fixture
def editing_api() -> Iterator[tuple[TestClient, dict[str, dict[str, str]]]]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        Feedback.__table__,
        Version.__table__,
        Requirement.__table__,
    ):
        table.create(engine)

    with Session(engine, expire_on_commit=False) as session:
        editor_role = Role(id=1, code="EDITOR", name="编辑者", data_scope=DataScope.SELF)
        viewer_role = Role(id=2, code="VIEWER", name="只读者", data_scope=DataScope.SELF)
        codes = (
            "rd.feedback.edit",
            "rd.feedback.view",
            "rd.requirement.edit",
            "rd.version.edit",
        )
        permissions = {
            code: Permission(id=i, code=code, name=code) for i, code in enumerate(codes, 1)
        }
        editor = User(
            id=1,
            username="editor",
            display_name="Editor",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        viewer = User(
            id=2,
            username="viewer",
            display_name="Viewer",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        outside_owner = User(
            id=3,
            username="outside",
            display_name="Outside",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        session.add_all(
            [editor_role, viewer_role, *permissions.values(), editor, viewer, outside_owner]
        )
        session.flush()
        session.add_all(
            [
                *(
                    RolePermission(role_id=editor_role.id, permission_id=p.id)
                    for p in permissions.values()
                ),
                RolePermission(
                    role_id=viewer_role.id,
                    permission_id=permissions["rd.feedback.view"].id,
                ),
                UserRole(user_id=editor.id, role_id=editor_role.id),
                UserRole(user_id=viewer.id, role_id=viewer_role.id),
            ]
        )
        session.add_all(
            [
                Feedback(
                    id=1,
                    feedback_no="FB-OUTSIDE",
                    title="外部反馈",
                    feedback_type=FeedbackType.SYSTEM_ISSUE,
                    urgency=FeedbackUrgency.NORMAL,
                    status=FeedbackStatus.NEW,
                    submitter_id=outside_owner.id,
                    description="description",
                    created_by=outside_owner.id,
                ),
                Requirement(
                    id=1,
                    requirement_no="REQ-OUTSIDE",
                    title="外部需求",
                    requirement_type="FEATURE",
                    source=RequirementSource.DIRECT,
                    priority=Priority.P2,
                    status=RequirementStatus.DRAFT,
                    description="description",
                    created_by=outside_owner.id,
                ),
                Requirement(
                    id=2,
                    requirement_no="REQ-OWN",
                    title="本人需求",
                    requirement_type="FEATURE",
                    source=RequirementSource.DIRECT,
                    priority=Priority.P2,
                    status=RequirementStatus.DRAFT,
                    description="description",
                    created_by=editor.id,
                ),
                Version(
                    id=1,
                    version_no="V-OUTSIDE",
                    name="外部版本",
                    status=VersionStatus.PLANNING,
                    created_by=outside_owner.id,
                ),
            ]
        )
        session.commit()

        headers = {
            name: {"Authorization": f"Bearer {create_access_token(user_id)}"}
            for name, user_id in {"editor": editor.id, "viewer": viewer.id}.items()
        }
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, headers
        app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize(
    "entity_type,entity_id", [("FEEDBACK", 1), ("REQUIREMENT", 1), ("VERSION", 1)]
)
@pytest.mark.parametrize("operation", ["start", "heartbeat", "end"])
def test_out_of_scope_editing_requests_never_touch_redis(
    editing_api, monkeypatch: pytest.MonkeyPatch, entity_type: str, entity_id: int, operation: str
) -> None:
    client, headers = editing_api
    redis_keys = {f"edit_lock:{entity_type}:{entity_id}": "existing-owner"}

    def forbidden_redis_access(self):
        pytest.fail("Rejected editing requests must not initialize or touch Redis")

    monkeypatch.setattr(EditingService, "__init__", forbidden_redis_access)
    response = client.post(
        f"/api/v1/editing/{operation}",
        headers=headers["editor"],
        json={"entity_type": entity_type, "entity_id": entity_id},
    )
    assert response.status_code == 404
    assert redis_keys == {f"edit_lock:{entity_type}:{entity_id}": "existing-owner"}


def test_read_only_user_cannot_start_editing_presence(editing_api, monkeypatch) -> None:
    client, headers = editing_api

    def forbidden_redis_access(self):
        pytest.fail("Permission failures must happen before Redis access")

    monkeypatch.setattr(EditingService, "__init__", forbidden_redis_access)
    response = client.post(
        "/api/v1/editing/start",
        headers=headers["viewer"],
        json={"entity_type": "FEEDBACK", "entity_id": 1},
    )
    assert response.status_code == 403


def test_editing_presence_can_start_for_in_scope_mutable_entity(editing_api, monkeypatch) -> None:
    client, headers = editing_api
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(EditingService, "__init__", lambda self: None)
    monkeypatch.setattr(
        EditingService,
        "start",
        lambda self, entity_type, entity_id, user_id, display_name, ttl_seconds=600: calls.append(
            (entity_type, entity_id)
        ),
    )
    response = client.post(
        "/api/v1/editing/start",
        headers=headers["editor"],
        json={"entity_type": "REQUIREMENT", "entity_id": 2},
    )
    assert response.status_code == 200
    assert calls == [("REQUIREMENT", 2)]

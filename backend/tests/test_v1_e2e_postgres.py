from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.cli.seed import PERMISSIONS as SEEDED_PERMISSIONS
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.entities import (
    Feedback,
    Notification,
    OperationLog,
    Permission,
    Release,
    Requirement,
    RequirementFeedback,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
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
from app.services.audit_service import AuditService

POSTGRES_URL = os.getenv("ITERFLOW_TEST_POSTGRES_URL")
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def postgres_e2e_engine() -> Iterator[tuple[Engine, int, dict[str, str]]]:
    if not POSTGRES_URL:
        pytest.skip("set ITERFLOW_TEST_POSTGRES_URL to run PostgreSQL HTTP acceptance tests")

    schema = f"phase82_e2e_{uuid4().hex}"
    admin_engine = create_engine(POSTGRES_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    database_url = make_url(POSTGRES_URL)
    env_names = {"DATABASE_URL", "PGOPTIONS"}
    old_env = {name: os.environ.get(name) for name in env_names}
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    os.environ["PGOPTIONS"] = f"-c search_path={schema}"
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_engine(
            POSTGRES_URL,
            connect_args={"options": f"-csearch_path={schema}"},
            pool_size=8,
            max_overflow=4,
        )
        with Session(engine) as session:
            permission = Permission(code="*", name="All capabilities")
            role = Role(
                code=f"E2E_{uuid4().hex[:8]}",
                name="HTTP acceptance administrator",
                data_scope=DataScope.ALL,
                enabled=True,
                is_system=True,
            )
            super_admin_role = Role(
                code="SUPER_ADMIN",
                name="超级管理员",
                data_scope=DataScope.ALL,
                enabled=True,
                is_system=True,
            )
            user = User(
                username=f"e2e-{uuid4().hex[:8]}",
                display_name="Phase 8.2 E2E",
                password_hash=hash_password("RA-Admin-Strong-Password"),
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            session.add_all(
                [permission, role, super_admin_role, user]
                + [Permission(code=code, name=name) for code, name in SEEDED_PERMISSIONS.items()]
            )
            session.flush()
            session.add_all(
                [
                    RolePermission(role_id=role.id, permission_id=permission.id),
                    UserRole(user_id=user.id, role_id=role.id),
                    UserRole(user_id=user.id, role_id=super_admin_role.id),
                ]
            )
            session.commit()
            user_id = user.id

        headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
        yield engine, user_id, headers
    finally:
        if "engine" in locals():
            engine.dispose()
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def postgres_http_client(postgres_e2e_engine):
    engine, _user_id, _headers = postgres_e2e_engine

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_full_v1_business_lifecycle_over_http_and_postgresql(
    postgres_http_client: TestClient,
    postgres_e2e_engine: tuple[Engine, int, dict[str, str]],
) -> None:
    client = postgres_http_client
    engine, user_id, headers = postgres_e2e_engine

    feedback_response = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "Phase 8.2 real HTTP feedback",
            "feedback_type": "NEW_FEATURE",
            "urgency": "NORMAL",
            "description": "Exercise the complete production business workflow.",
        },
    )
    assert feedback_response.status_code == 200, feedback_response.text
    feedback = feedback_response.json()
    assert feedback["status"] == "NEW"

    accepted = client.patch(
        f"/api/v1/feedbacks/{feedback['id']}/status",
        headers=headers,
        json={"status": "ACCEPTED", "revision": feedback["revision"]},
    )
    assert accepted.status_code == 200, accepted.text

    converted = client.post(
        f"/api/v1/feedbacks/{feedback['id']}/convert",
        headers=headers,
        json={
            "type": "CREATE_NEW",
            "revision": accepted.json()["revision"],
            "requirement_title": "Phase 8.2 converted requirement",
            "requirement_type": "FEATURE",
            "priority": "P2",
            "description": "Requirement created through feedback conversion.",
        },
    )
    assert converted.status_code == 200, converted.text
    requirement = converted.json()
    assert requirement["source"] == "FEEDBACK"
    assert requirement["status"] == "CONFIRMED"

    version_response = client.post(
        "/api/v1/versions",
        headers=headers,
        json={"version_no": f"8.2-{uuid4().hex[:8]}", "name": "Phase 8.2 acceptance"},
    )
    assert version_response.status_code == 200, version_response.text
    version = version_response.json()

    member_response = client.post(
        f"/api/v1/versions/{version['id']}/requirements",
        headers=headers,
        json={
            "requirement_id": requirement["id"],
            "revision": requirement["revision"],
            "version_revision": version["revision"],
        },
    )
    assert member_response.status_code == 200, member_response.text
    version = member_response.json()

    planned_response = client.get(f"/api/v1/requirements/{requirement['id']}", headers=headers)
    assert planned_response.status_code == 200, planned_response.text
    current_requirement = planned_response.json()
    assert current_requirement["status"] == "PLANNED"
    for status in ("DEVELOPING", "TESTING", "DONE"):
        response = client.patch(
            f"/api/v1/requirements/{requirement['id']}/status",
            headers=headers,
            json={"status": status, "revision": current_requirement["revision"]},
        )
        assert response.status_code == 200, response.text
        current_requirement = response.json()

    for status in ("DEVELOPING", "TESTING", "READY"):
        response = client.patch(
            f"/api/v1/versions/{version['id']}/status",
            headers=headers,
            json={"status": status, "revision": version["revision"]},
        )
        assert response.status_code == 200, response.text
        version = response.json()

    publish_check = client.post(f"/api/v1/versions/{version['id']}/publish/check", headers=headers)
    assert publish_check.status_code == 200, publish_check.text
    assert publish_check.json()["passed"] is True

    published = client.post(
        f"/api/v1/versions/{version['id']}/publish",
        headers=headers,
        json={
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": "Phase 8.2 PostgreSQL end-to-end acceptance.",
            "revision": version["revision"],
        },
    )
    assert published.status_code == 200, published.text
    result = published.json()
    release_id = result["release"]["id"]
    assert result["release"]["result"] == "SUCCESS"
    assert result["released_requirement_ids"] == [requirement["id"]]
    assert result["online_feedback_ids"] == [feedback["id"]]

    release_list = client.get("/api/v1/releases", headers=headers)
    release_detail = client.get(f"/api/v1/releases/{release_id}", headers=headers)
    version_requirements = client.get(
        f"/api/v1/versions/{version['id']}/requirements", headers=headers
    )
    requirement_feedbacks = client.get(
        f"/api/v1/requirements/{requirement['id']}/feedbacks", headers=headers
    )
    assert release_list.status_code == 200, release_list.text
    assert release_detail.status_code == 200, release_detail.text
    assert version_requirements.status_code == 200, version_requirements.text
    assert requirement_feedbacks.status_code == 200, requirement_feedbacks.text
    assert any(item["id"] == release_id for item in release_list.json()["items"])
    assert release_detail.json()["version_id"] == version["id"]
    assert version_requirements.json()["items"][0]["id"] == requirement["id"]
    assert requirement_feedbacks.json()[0]["feedback_id"] == feedback["id"]

    with Session(engine) as session:
        final_feedback = session.get(Feedback, feedback["id"])
        final_requirement = session.get(Requirement, requirement["id"])
        final_version = session.get(Version, version["id"])
        final_release = session.get(Release, release_id)
        assert final_feedback is not None and final_requirement is not None
        assert final_version is not None and final_release is not None
        assert final_version.status == VersionStatus.RELEASED
        assert final_requirement.status == RequirementStatus.ONLINE
        assert final_feedback.status == FeedbackStatus.ONLINE
        assert final_feedback.main_requirement_id == final_requirement.id
        assert final_requirement.current_version_id == final_version.id
        assert final_release.version_id == final_version.id
        assert (
            session.scalar(
                select(func.count(Release.id)).where(Release.version_id == final_version.id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(VersionRequirement.id)).where(
                    VersionRequirement.requirement_id == final_requirement.id,
                    VersionRequirement.active.is_(True),
                    VersionRequirement.version_id == final_version.id,
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(RequirementFeedback.id)).where(
                    RequirementFeedback.feedback_id == final_feedback.id,
                    RequirementFeedback.requirement_id == final_requirement.id,
                    RequirementFeedback.is_primary.is_(True),
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.entity_type == "VERSION",
                    OperationLog.entity_id == final_version.id,
                    OperationLog.action == "VERSION_PUBLISH",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.entity_type == "FEEDBACK",
                    Notification.entity_id == final_feedback.id,
                )
            )
            == 1
        )


def test_concurrent_publish_has_one_http_winner_and_no_duplicate_side_effects(
    postgres_http_client: TestClient,
    postgres_e2e_engine: tuple[Engine, int, dict[str, str]],
) -> None:
    engine, user_id, headers = postgres_e2e_engine
    version = Version(
        version_no=f"RACE-{uuid4().hex[:8]}",
        name="Concurrent publish acceptance",
        status=VersionStatus.READY,
        created_by=user_id,
        updated_by=user_id,
    )
    requirement = Requirement(
        requirement_no=f"REQ-{uuid4().hex[:8]}",
        title="Concurrent publish requirement",
        requirement_type="FEATURE",
        source=RequirementSource.DIRECT,
        priority=Priority.P2,
        status=RequirementStatus.DONE,
        description="A completed requirement for concurrent publish.",
        owner_id=user_id,
        created_by=user_id,
        updated_by=user_id,
    )
    feedback = Feedback(
        feedback_no=f"FB-{uuid4().hex[:8]}",
        title="Concurrent publish feedback",
        feedback_type=FeedbackType.NEW_FEATURE,
        urgency=FeedbackUrgency.NORMAL,
        status=FeedbackStatus.REQUIREMENT_LINKED,
        submitter_id=user_id,
        description="Feedback should transition once.",
        created_by=user_id,
        updated_by=user_id,
    )
    with Session(engine) as session:
        session.add_all([version, requirement, feedback])
        session.flush()
        requirement.current_version_id = version.id
        feedback.main_requirement_id = requirement.id
        session.add_all(
            [
                VersionRequirement(
                    version_id=version.id,
                    requirement_id=requirement.id,
                    active=True,
                    added_by=user_id,
                ),
                RequirementFeedback(
                    requirement_id=requirement.id,
                    feedback_id=feedback.id,
                    is_primary=True,
                ),
            ]
        )
        session.commit()
        version_id = version.id
        expected_revision = version.revision
        requirement_id = requirement.id
        feedback_id = feedback.id

    barrier = Barrier(2)

    def publish_once() -> int:
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            response = client.post(
                f"/api/v1/versions/{version_id}/publish",
                headers=headers,
                json={
                    "released_at": datetime.now(UTC).isoformat(),
                    "release_notes": "Concurrent publish race.",
                    "revision": expected_revision,
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _index: publish_once(), range(2)))
    assert sorted(statuses) == [200, 409]

    with Session(engine) as session:
        final_version = session.get(Version, version_id)
        final_requirement = session.get(Requirement, requirement_id)
        final_feedback = session.get(Feedback, feedback_id)
        assert final_version is not None and final_requirement is not None
        assert final_feedback is not None
        assert final_version.status == VersionStatus.RELEASED
        assert final_requirement.status == RequirementStatus.ONLINE
        assert final_feedback.status == FeedbackStatus.ONLINE
        assert (
            session.scalar(select(func.count(Release.id)).where(Release.version_id == version_id))
            == 1
        )
        assert (
            session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.entity_id == feedback_id,
                    Notification.entity_type == "FEEDBACK",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.entity_type == "VERSION",
                    OperationLog.entity_id == version_id,
                    OperationLog.action == "VERSION_PUBLISH",
                )
            )
            == 1
        )


def test_v15_release_acceptance_with_real_users_and_postgresql(
    postgres_http_client: TestClient,
    postgres_e2e_engine: tuple[Engine, int, dict[str, str]],
) -> None:
    client = postgres_http_client
    engine, _admin_id, _headers = postgres_e2e_engine
    prefix = f"RA-{uuid4().hex[:8]}"
    password = f"RA-Strong-{uuid4().hex}"

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": _headers_user(engine, _admin_id), "password": "RA-Admin-Strong-Password"},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    catalog = client.get("/api/v1/roles/permissions", headers=admin)
    assert catalog.status_code == 200, catalog.text
    permission_ids = {item["code"]: item["id"] for item in catalog.json()}
    # The isolated fixture uses the same production permission catalog, while
    # test-specific roles and users are created only through public APIs.
    approver_codes = (
        "rd.feedback.view",
        "rd.feedback.edit",
        "rd.feedback.convert",
        "rd.requirement.view",
        "rd.requirement.edit",
        "rd.requirement.status",
        "rd.version.view",
        "rd.version.edit",
        "rd.version.status",
    )
    approver_role = client.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "code": f"{prefix}_APPROVER",
            "name": "RA 负责人",
            "data_scope": "ALL",
            "permission_ids": [permission_ids[code] for code in approver_codes],
        },
    )
    assert approver_role.status_code == 200, approver_role.text
    member_role = client.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "code": f"{prefix}_MEMBER",
            "name": "RA 成员",
            "data_scope": "SELF",
            "permission_ids": [
                permission_ids[code]
                for code in ("rd.feedback.view", "rd.feedback.create", "rd.requirement.view")
            ],
        },
    )
    assert member_role.status_code == 200, member_role.text

    def create_user(suffix: str, role_id: int) -> tuple[int, dict[str, str]]:
        username = f"{prefix}-{suffix}".lower()
        response = client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "username": username,
                "display_name": username,
                "password": password,
                "role_ids": [role_id],
            },
        )
        assert response.status_code == 200, response.text
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200, login.text
        changed = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={"current_password": password, "new_password": f"{password}-changed"},
        )
        assert changed.status_code == 200, changed.text
        return response.json()["id"], {"Authorization": f"Bearer {changed.json()['access_token']}"}

    submitter_id, member = create_user("member", member_role.json()["id"])
    approver_id, approver = create_user("approver", approver_role.json()["id"])
    outsider_id, outsider = create_user("outsider", member_role.json()["id"])
    assert outsider_id != submitter_id

    created = client.post(
        "/api/v1/feedbacks",
        headers=member,
        json={
            "title": f"{prefix} 原始反馈",
            "feedback_type": "NEW_FEATURE",
            "description": "V1.5 正式发布验收反馈",
        },
    )
    assert created.status_code == 200, created.text
    feedback = created.json()
    feedback_id = feedback["id"]
    assert client.get(f"/api/v1/feedbacks/{feedback_id}", headers=outsider).status_code == 404
    accepted = client.patch(
        f"/api/v1/feedbacks/{feedback_id}/status",
        headers=approver,
        json={"status": "ACCEPTED", "revision": feedback["revision"]},
    )
    assert accepted.status_code == 200, accepted.text
    converted = client.post(
        f"/api/v1/feedbacks/{feedback_id}/convert",
        headers=approver,
        json={
            "type": "CREATE_NEW",
            "revision": accepted.json()["revision"],
            "requirement_title": f"{prefix} 正式需求",
            "requirement_type": "FEATURE",
            "description": "V1.5 正式发布验收需求",
            "acceptance_criteria": "通过正式验收",
        },
    )
    assert converted.status_code == 200, converted.text
    requirement = converted.json()
    requirement_id = requirement["id"]
    duplicate = client.post(
        f"/api/v1/feedbacks/{feedback_id}/convert",
        headers=approver,
        json={
            "type": "CREATE_NEW",
            "revision": accepted.json()["revision"],
            "requirement_title": "重复需求",
            "requirement_type": "FEATURE",
            "description": "不应留下半成品",
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    first_read = client.get(f"/api/v1/requirements/{requirement_id}", headers=admin).json()
    second_read = client.get(f"/api/v1/requirements/{requirement_id}", headers=approver).json()
    assert first_read["revision"] == second_read["revision"]
    winning = client.patch(
        f"/api/v1/requirements/{requirement_id}",
        headers=admin,
        json={"priority": "P1", "revision": first_read["revision"]},
    )
    assert winning.status_code == 200, winning.text
    stale = client.patch(
        f"/api/v1/requirements/{requirement_id}",
        headers=approver,
        json={"priority": "P3", "revision": second_read["revision"]},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["data"]["current_revision"] == winning.json()["revision"]
    assert (
        client.get(f"/api/v1/requirements/{requirement_id}", headers=admin).json()["priority"]
        == "P1"
    )
    assigned = client.patch(
        f"/api/v1/requirements/{requirement_id}",
        headers=approver,
        json={
            "owner_id": approver_id,
            "acceptance_criteria": "通过正式验收",
            "revision": winning.json()["revision"],
        },
    )
    assert assigned.status_code == 200, assigned.text
    requirement = assigned.json()

    version_response = client.post(
        "/api/v1/versions",
        headers=admin,
        json={"version_no": f"{prefix}-V1.0.1", "name": f"{prefix} 正式验收版本"},
    )
    assert version_response.status_code == 200, version_response.text
    version = version_response.json()
    added = client.post(
        f"/api/v1/versions/{version['id']}/requirements",
        headers=admin,
        json={
            "requirement_id": requirement_id,
            "revision": requirement["revision"],
            "version_revision": version["revision"],
        },
    )
    assert added.status_code == 200, added.text
    version = added.json()
    requirement = client.get(f"/api/v1/requirements/{requirement_id}", headers=admin).json()
    assert requirement["status"] == "PLANNED"
    for status in ("DEVELOPING", "TESTING", "DONE"):
        response = client.patch(
            f"/api/v1/requirements/{requirement_id}/status",
            headers=approver,
            json={"status": status, "revision": requirement["revision"]},
        )
        assert response.status_code == 200, response.text
        requirement = response.json()
    for status in ("DEVELOPING", "TESTING", "READY"):
        response = client.patch(
            f"/api/v1/versions/{version['id']}/status",
            headers=admin,
            json={"status": status, "revision": version["revision"]},
        )
        assert response.status_code == 200, response.text
        version = response.json()
    check = client.post(f"/api/v1/versions/{version['id']}/publish/check", headers=admin)
    assert check.status_code == 200 and check.json()["passed"] is True, check.text
    published = client.post(
        f"/api/v1/versions/{version['id']}/publish",
        headers={**admin, "X-Request-ID": "ra-release-acceptance"},
        json={
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": f"{prefix} 发布验收",
            "revision": version["revision"],
        },
    )
    assert published.status_code == 200, published.text
    release_id = published.json()["release"]["id"]
    assert published.json()["release"]["result"] == "SUCCESS"
    assert client.get(f"/api/v1/releases/{release_id}", headers=admin).status_code == 200
    assert (
        client.get(f"/api/v1/versions/{version['id']}", headers=admin).json()["status"]
        == "RELEASED"
    )
    assert (
        client.get(f"/api/v1/requirements/{requirement_id}", headers=admin).json()["status"]
        == "ONLINE"
    )
    assert (
        client.get(f"/api/v1/feedbacks/{feedback_id}", headers=member).json()["status"] == "ONLINE"
    )
    notifications = client.get("/api/v1/notifications?unread_only=true", headers=member)
    assert notifications.status_code == 200, notifications.text
    notice = next(item for item in notifications.json() if item["entity_id"] == feedback_id)
    assert notice["read_at"] is None and notice["entity_type"] == "FEEDBACK"
    marked = client.post(f"/api/v1/notifications/{notice['id']}/read", headers=member)
    assert marked.status_code == 200, marked.text
    listed_after_read = client.get("/api/v1/notifications", headers=member)
    assert listed_after_read.status_code == 200, listed_after_read.text
    assert (
        next(item for item in listed_after_read.json() if item["id"] == notice["id"])["read_at"]
        is not None
    )

    with Session(engine) as session:
        fb = session.get(Feedback, feedback_id)
        req = session.get(Requirement, requirement_id)
        assert fb is not None and req is not None
        assert fb.main_requirement_id == requirement_id
        assert req.current_version_id == version["id"]
        assert (
            session.scalar(
                select(func.count(RequirementFeedback.id)).where(
                    RequirementFeedback.feedback_id == feedback_id,
                    RequirementFeedback.is_primary.is_(True),
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(Release.id)).where(Release.version_id == version["id"])
            )
            == 1
        )
        logs = session.scalars(
            select(OperationLog).where(OperationLog.request_id == "ra-release-acceptance")
        ).all()
        assert {log.action for log in logs} >= {"VERSION_PUBLISH", "RELEASE_CREATE"}
        assert all(log.operator_id == _admin_id and log.ip_address for log in logs)
        assert all(log.user_agent for log in logs)
        all_logs = session.scalars(select(OperationLog)).all()
        expected_actions = {
            ("ROLE", "ROLE_CREATE"),
            ("USER", "CREATE"),
            ("FEEDBACK", "CREATE"),
            ("FEEDBACK", "STATUS_CHANGE"),
            ("FEEDBACK", "CONVERT_REQUIREMENT"),
            ("REQUIREMENT", "CREATE_FROM_FEEDBACK"),
            ("REQUIREMENT", "STATUS_CHANGE"),
            ("VERSION", "CREATE"),
            ("VERSION", "VERSION_REQUIREMENT_ADD"),
            ("VERSION", "STATUS_CHANGE"),
            ("VERSION", "VERSION_PUBLISH"),
            ("RELEASE", "RELEASE_CREATE"),
        }
        assert expected_actions <= {(log.entity_type, log.action) for log in all_logs}
        for entity_type, action in expected_actions:
            log = next(
                item
                for item in all_logs
                if item.entity_type == entity_type and item.action == action
            )
            assert log.operator_id is not None
            assert log.request_id and log.ip_address and log.user_agent
            assert log.after_data is not None
        version_status_log = next(
            log
            for log in all_logs
            if log.entity_type == "VERSION" and log.action == "STATUS_CHANGE"
        )
        feedback_convert_log = next(
            log
            for log in all_logs
            if log.entity_type == "FEEDBACK" and log.action == "CONVERT_REQUIREMENT"
        )
        assert version_status_log.before_data is not None
        assert feedback_convert_log.before_data is not None
        assert (
            session.scalar(
                select(func.count(Requirement.id)).where(Requirement.title == "重复需求")
            )
            == 0
        )
    audit = client.get(
        "/api/v1/audits",
        headers=admin,
        params={"entity_type": "VERSION", "entity_id": version["id"], "action": "VERSION_PUBLISH"},
    )
    assert audit.status_code == 200 and audit.json()["total"] == 1, audit.text
    assert audit.json()["items"][0]["operator"] is not None
    assert audit.json()["items"][0]["before"]["status"] == "READY"
    assert audit.json()["items"][0]["after"]["status"] == "RELEASED"


def _headers_user(engine: Engine, user_id: int) -> str:
    with Session(engine) as session:
        user = session.get(User, user_id)
        assert user is not None
        return user.username


def test_v15_publish_fault_rolls_back_all_side_effects(
    postgres_http_client: TestClient,
    postgres_e2e_engine: tuple[Engine, int, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = postgres_http_client
    engine, user_id, headers = postgres_e2e_engine
    marker = f"RA-ROLLBACK-{uuid4().hex[:8]}"
    with Session(engine) as session:
        version = Version(
            version_no=marker,
            name=marker,
            status=VersionStatus.READY,
            created_by=user_id,
            updated_by=user_id,
        )
        requirement = Requirement(
            requirement_no=f"REQ-{marker}",
            title=marker,
            requirement_type="FEATURE",
            source=RequirementSource.DIRECT,
            priority=Priority.P2,
            status=RequirementStatus.DONE,
            description=marker,
            owner_id=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        feedback = Feedback(
            feedback_no=f"FB-{marker}",
            title=marker,
            feedback_type=FeedbackType.NEW_FEATURE,
            urgency=FeedbackUrgency.NORMAL,
            status=FeedbackStatus.REQUIREMENT_LINKED,
            submitter_id=user_id,
            description=marker,
            created_by=user_id,
            updated_by=user_id,
        )
        session.add_all([version, requirement, feedback])
        session.flush()
        requirement.current_version_id = version.id
        feedback.main_requirement_id = requirement.id
        session.add_all(
            [
                VersionRequirement(
                    version_id=version.id,
                    requirement_id=requirement.id,
                    active=True,
                    added_by=user_id,
                ),
                RequirementFeedback(
                    requirement_id=requirement.id, feedback_id=feedback.id, is_primary=True
                ),
            ]
        )
        session.commit()
        version_id, requirement_id, feedback_id = version.id, requirement.id, feedback.id
        revision = version.revision

    original_log = AuditService.log

    def fail_on_release_audit(self, entity_type, entity_id, action, *args, **kwargs):
        if action == "RELEASE_CREATE":
            raise RuntimeError("RA controlled publish fault")
        return original_log(self, entity_type, entity_id, action, *args, **kwargs)

    monkeypatch.setattr(AuditService, "log", fail_on_release_audit)
    response = client.post(
        f"/api/v1/versions/{version_id}/publish",
        headers=headers,
        json={
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": marker,
            "revision": revision,
        },
    )
    assert response.status_code == 500, response.text
    with Session(engine) as session:
        assert session.get(Version, version_id).status == VersionStatus.READY
        assert session.get(Requirement, requirement_id).status == RequirementStatus.DONE
        assert session.get(Feedback, feedback_id).status == FeedbackStatus.REQUIREMENT_LINKED
        assert (
            session.scalar(select(func.count(Release.id)).where(Release.version_id == version_id))
            == 0
        )
        assert (
            session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.entity_type == "FEEDBACK",
                    Notification.entity_id == feedback_id,
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.entity_type == "VERSION",
                    OperationLog.entity_id == version_id,
                    OperationLog.action == "VERSION_PUBLISH",
                )
            )
            == 0
        )

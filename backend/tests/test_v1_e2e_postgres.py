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
from system_binding_fixture import create_test_system

from alembic import command
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    Notification,
    OperationLog,
    Permission,
    Release,
    Requirement,
    RequirementFeedback,
    RequirementStep,
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
            user = User(
                username=f"e2e-{uuid4().hex[:8]}",
                display_name="Phase 8.2 E2E",
                password_hash="unused-test-digest",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            session.add_all([permission, role, user])
            session.flush()
            session.add_all(
                [
                    RolePermission(role_id=role.id, permission_id=permission.id),
                    UserRole(user_id=user.id, role_id=role.id),
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


def assert_feedback_accept_conversion(client, engine, headers, user_id, feedback, requirement):
    path = f"/api/v1/feedbacks/{feedback['id']}"
    detail = client.get(path, headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "REQUIREMENT_LINKED"
    assert detail.json()["main_requirement_id"] == requirement["id"]
    assert detail.json()["revision"] == feedback["revision"] + 1
    collaboration = client.get(f"{path}/collaboration", headers=headers)
    assert collaboration.status_code == 200, collaboration.text
    assert collaboration.json()["handler_id"] == collaboration.json()["accepted_by"] == user_id
    assert collaboration.json()["accepted_at"]

    with Session(engine) as session:
        conversion = session.scalars(
            select(OperationLog).where(
                OperationLog.entity_type == "FEEDBACK",
                OperationLog.entity_id == feedback["id"],
                OperationLog.action == "CONVERT_REQUIREMENT",
            )
        ).one()
        assert conversion.operator_id == user_id
        assert conversion.before_data["status"] == "NEW"
        assert conversion.after_data["status"] == "REQUIREMENT_LINKED"
        assert conversion.after_data["requirement_id"] == requirement["id"]
        assert conversion.after_data["accept_on_convert"] is True
        assert (
            conversion.after_data["handler_id"] == conversion.after_data["accepted_by"] == user_id
        )
        assert conversion.after_data["accepted_at"]
        feedback_events = session.scalars(
            select(CollaborationEvent).where(
                CollaborationEvent.entity_type == "FEEDBACK",
                CollaborationEvent.entity_id == feedback["id"],
                CollaborationEvent.action.in_(("STATUS_ACCEPTED", "STATUS_REQUIREMENT_LINKED")),
            )
        ).all()
        assert [(row.action, row.actor_id, row.recipient_ids) for row in feedback_events] == [
            ("STATUS_REQUIREMENT_LINKED", user_id, [user_id])
        ]
        requirement_event = session.scalars(
            select(CollaborationEvent).where(
                CollaborationEvent.entity_type == "REQUIREMENT",
                CollaborationEvent.entity_id == requirement["id"],
                CollaborationEvent.action == "CREATED",
            )
        ).one()
        assert requirement_event.actor_id == user_id
        assert requirement_event.recipient_ids == [user_id]


def advance_requirement_to_ready(
    client, engine, headers, user_id, feedback, requirement, version, *, complete_and_accept
):
    path = f"/api/v1/requirements/{requirement['id']}"
    version_path = f"/api/v1/versions/{version['id']}"
    progress_by_status = {
        "CONFIRMED": "PLANNING",
        "DEVELOPING": "DEVELOPING",
        "TESTING": "TESTING",
        "DONE": "READY",
    }
    statuses = ("CONFIRMED", "DEVELOPING") if complete_and_accept else tuple(progress_by_status)
    for status in statuses:
        response = client.patch(
            path + "/status",
            headers=headers,
            json={"status": status, "revision": requirement["revision"]},
        )
        assert response.status_code == 200, response.text
        requirement = response.json()
        progress = client.get(version_path, headers=headers).json()
        assert progress["status"] == progress_by_status[status]
        assert progress["revision"] == version["revision"]
    if not complete_and_accept:
        return

    revision = requirement["revision"]
    direct_status = client.patch(
        path + "/status", headers=headers, json={"status": "DONE", "revision": revision}
    )
    assert direct_status.status_code == 409 and direct_status.json()["code"] == 40911
    reason = "开发完成并通过验收"
    payload = {"action": "COMPLETE_AND_ACCEPT", "revision": revision, "reason": reason}
    barrier = Barrier(2)

    def complete(_index):
        barrier.wait()
        return client.post(path + "/workflow", headers=headers, json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        completed, stale = sorted(
            pool.map(complete, range(2)), key=lambda result: result.status_code
        )
    assert completed.status_code == 200, completed.text
    assert completed.json()["revision"] == revision + 1
    assert stale.status_code == 409 and stale.json()["code"] == 40910, stale.text
    assert stale.json()["data"]["current_revision"] == revision + 1
    assert stale.json()["data"]["current_updated_by"] == user_id
    repeated = client.post(
        path + "/workflow", headers=headers, json={**payload, "revision": revision + 1}
    )
    assert repeated.status_code == 409 and repeated.json()["code"] == 40961, repeated.text
    current = client.get(path, headers=headers).json()
    assert current["status"] == "DONE" and current["revision"] == revision + 1
    progress = client.get(version_path, headers=headers).json()
    assert progress["status"] == "READY" and progress["revision"] == version["revision"]

    with Session(engine) as session:
        steps = session.scalars(
            select(RequirementStep).where(
                RequirementStep.requirement_id == requirement["id"],
                RequirementStep.action.in_(("STATUS_TESTING", "STATUS_DONE")),
            )
        ).all()
        assert len(steps) == 2
        assert {(step.action, step.detail["from"], step.detail["to"]) for step in steps} == {
            ("STATUS_TESTING", "DEVELOPING", "TESTING"),
            ("STATUS_DONE", "TESTING", "DONE"),
        }
        assert len({step.id for step in steps}) == 2
        actor = session.get(User, user_id)
        for step in steps:
            assert step.actor_id == user_id and step.created_at
            assert step.detail["actor_name"] == actor.display_name
            assert step.detail["source"] == payload["action"] and step.detail["reason"] == reason
            assert step.detail["content_revision"] == completed.json()["content_revision"]
            for field in ("description", "description_format", "acceptance_criteria"):
                assert step.detail[field] == requirement[field]
            assert {(p["role"], p["user_id"]) for p in step.detail["participants"]} == {
                (role, user_id) for role in ("CONFIRM", "DEVELOP", "ACCEPT")
            }
        logs = session.scalars(
            select(OperationLog).where(
                OperationLog.entity_type == "REQUIREMENT",
                OperationLog.entity_id == requirement["id"],
                OperationLog.action == "STATUS_CHANGE",
            )
        ).all()
        assert len(logs) == 3
        shortcut = next(log for log in logs if log.after_data["status"] == "DONE")
        assert shortcut.operator_id == user_id
        assert shortcut.before_data == {"status": "DEVELOPING"}
        assert shortcut.after_data == {
            "status": "DONE",
            "via": "TESTING",
            "source": payload["action"],
            "reason": reason,
        }
        assert all(log.after_data["status"] != "TESTING" for log in logs)
        for kind, entity_id, prefix in (
            ("REQUIREMENT", requirement["id"], ""),
            ("FEEDBACK", feedback["id"], "REQUIREMENT_"),
        ):
            events = session.scalars(
                select(CollaborationEvent).where(
                    CollaborationEvent.entity_type == kind,
                    CollaborationEvent.entity_id == entity_id,
                    CollaborationEvent.action.in_(
                        (prefix + "STATUS_TESTING", prefix + "STATUS_DONE")
                    ),
                )
            ).all()
            assert [(event.action, event.actor_id, event.recipient_ids) for event in events] == [
                (prefix + "STATUS_DONE", user_id, [user_id])
            ]


@pytest.mark.parametrize("complete_and_accept", [False, True], ids=["separate", "one-step"])
def test_full_v1_business_lifecycle_over_http_and_postgresql(
    postgres_http_client: TestClient,
    postgres_e2e_engine: tuple[Engine, int, dict[str, str]],
    complete_and_accept: bool,
) -> None:
    client = postgres_http_client
    engine, user_id, headers = postgres_e2e_engine
    system_id = create_test_system(engine)

    feedback_response = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "Phase 8.2 real HTTP feedback",
            "system_id": system_id,
            "feedback_type": "NEW_FEATURE",
            "recipient_ids": [user_id],
            "urgency": "NORMAL",
            "description": "Exercise the complete production business workflow.",
        },
    )
    assert feedback_response.status_code == 200, feedback_response.text
    feedback = feedback_response.json()
    assert feedback["status"] == "NEW"

    converted = client.post(
        f"/api/v1/feedbacks/{feedback['id']}/accept-and-convert",
        headers=headers,
        json={
            "type": "CREATE_NEW",
            "revision": feedback["revision"],
            "accept_on_convert": True,
            "requirement_title": "Phase 8.2 converted requirement",
            "requirement_type": "FEATURE",
            "priority": "P2",
            "description": "Requirement created through feedback conversion.",
            "acceptance_criteria": "确认流程与实际发布记录",
            "participants": [{"role": "CONFIRM", "user_id": user_id}],
        },
    )
    assert converted.status_code == 200, converted.text
    requirement = converted.json()
    assert requirement["source"] == "FEEDBACK"
    assert requirement["status"] == "DRAFT"
    assert_feedback_accept_conversion(client, engine, headers, user_id, feedback, requirement)

    version_response = client.post(
        "/api/v1/versions",
        headers=headers,
        json={
            "system_id": system_id,
            "version_no": f"8.2-{uuid4().hex[:8]}",
            "name": "Phase 8.2 acceptance",
        },
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
    assert current_requirement["status"] == "DRAFT"
    assigned = client.put(
        f"/api/v1/requirements/{requirement['id']}/participants",
        headers=headers,
        json={
            "revision": current_requirement["revision"],
            "participants": [
                {"user_id": user_id, "role": role} for role in ("CONFIRM", "DEVELOP", "ACCEPT")
            ],
        },
    )
    assert assigned.status_code == 200, assigned.text
    current_requirement["revision"] = assigned.json()["revision"]
    advance_requirement_to_ready(
        client,
        engine,
        headers,
        user_id,
        feedback,
        current_requirement,
        version,
        complete_and_accept=complete_and_accept,
    )

    relation_revision = version["revision"]
    version = client.get(f"/api/v1/versions/{version['id']}", headers=headers).json()
    assert version["status"] == "READY"
    assert version["revision"] == relation_revision
    for status in ("DEVELOPING", "TESTING", "READY"):
        response = client.patch(
            f"/api/v1/versions/{version['id']}/status",
            headers=headers,
            json={"status": status, "revision": version["revision"]},
        )
        assert response.status_code == 409 and response.json()["code"] == 40921
    assert client.get(f"/api/v1/versions/{version['id']}", headers=headers).json() == version

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
    system_id = create_test_system(engine)
    version = Version(
        system_id=system_id,
        version_no=f"RACE-{uuid4().hex[:8]}",
        name="Concurrent publish acceptance",
        status=VersionStatus.READY,
        created_by=user_id,
        updated_by=user_id,
    )
    requirement = Requirement(
        system_id=system_id,
        legacy_completed=True,
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

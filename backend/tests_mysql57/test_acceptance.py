"""Real MySQL 5.7 application gates. Missing MySQL is a failure, never a skip."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from test_release_date_filters_postgres import dates as dates
from test_release_date_filters_postgres import (
    test_date_bounds_total_pagination_and_permission as _date_bounds,
)
from test_release_date_filters_postgres import (
    test_date_query_validation as _date_validation,
)
from test_v1_e2e_postgres import (
    test_concurrent_publish_has_one_http_winner_and_no_duplicate_side_effects as _publish_race,
)

from alembic import command
from app.cli.seed import seed_database
from app.core import database
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    Feedback,
    Notification,
    OperationLog,
    Release,
    Requirement,
    RequirementFeedback,
    RequirementParticipant,
    Role,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import FeedbackStatus, RequirementStatus, VersionStatus


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


BACKEND = Path(__file__).resolve().parents[1]
PORTABLE = os.environ.get("ITERFLOW_MYSQL_TEST_PROFILE") == "portable"
TEST_PORT = 57358 if PORTABLE else 57357
TEST_CONTAINER = "iterflow-mysql57-portable-db" if PORTABLE else "iterflow-mysql57-proof-db"
TEST_PROJECT = "iterflow-mysql57-portable" if PORTABLE else "iterflow-mysql57-proof"
TEST_VERSION = "5.7.44-log" if PORTABLE else "5.7.44"


@pytest.fixture
def mysql_api(monkeypatch, tmp_path):
    url = make_url(os.environ["DATABASE_URL"])
    assert url.drivername == "mysql+pymysql"
    assert url.host == "127.0.0.1" and url.port == TEST_PORT, "local dedicated container only"
    admin = create_engine(url, pool_pre_ping=True)
    name = "iterflow_mysql57_" + uuid4().hex
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT VERSION()")) == TEST_VERSION
        if PORTABLE:
            assert connection.execute(
                text("SELECT @@GLOBAL.innodb_large_prefix, @@GLOBAL.innodb_strict_mode")
            ).one() == (0, 0)
        connection.execute(
            text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        )
    test_url = url.set(database=name)
    monkeypatch.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    engine = create_engine(
        test_url, isolation_level="READ COMMITTED", pool_size=8, max_overflow=4, pool_pre_ping=True
    )
    event.listen(engine, "connect", database.configure_mysql)
    try:
        command.upgrade(Config(str(BACKEND / "alembic-mysql.ini")), "head")
        with Session(engine) as session:
            seed_database(session, username="test-admin", password="Fresh-test-password-57!")
            assert session.scalar(select(func.count(User.id))) == 1
            for model in (Feedback, Requirement, Version, Release, Notification):
                assert session.scalar(select(func.count(model.id))) == 0
            user = session.scalar(select(User).where(User.username == "test-admin"))
            user.must_change_password = False
            session.commit()
            user_id = user.id
        monkeypatch.setattr(
            database,
            "SessionLocal",
            sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        headers = RedactedHeaders(Authorization=f"Bearer {create_access_token(user_id)}")
        with TestClient(app) as client:
            yield client, engine, user_id, headers
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        get_settings.cache_clear()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()


def test_mysql_full_lifecycle(mysql_api):
    client, engine, _, _ = mysql_api
    logged = client.post(
        "/api/v1/auth/login", json={"username": "test-admin", "password": "Fresh-test-password-57!"}
    )
    assert logged.status_code == 200
    admin_headers = RedactedHeaders(Authorization="Bearer " + logged.json()["access_token"])
    permissions = client.get("/api/v1/roles/permissions", headers=admin_headers).json()
    role = client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={
            "code": "CHAIN_OPERATOR",
            "name": "主链验收角色",
            "data_scope": "ALL",
            "permission_ids": [p["id"] for p in permissions],
        },
    )
    assert role.status_code == 200, role.text
    user = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": "chain-user",
            "display_name": "主链提交人",
            "password": "New-chain-password-57!",
            "role_ids": [role.json()["id"]],
        },
    )
    assert user.status_code == 200, user.text
    user_id = user.json()["id"]
    pair = client.post(
        "/api/v1/auth/login", json={"username": "chain-user", "password": "New-chain-password-57!"}
    ).json()
    initial_headers = RedactedHeaders(Authorization="Bearer " + pair["access_token"])
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=initial_headers,
        json={
            "current_password": "New-chain-password-57!",
            "new_password": "Changed-chain-password-57!",
        },
    )
    assert changed.status_code == 200
    headers = RedactedHeaders(Authorization="Bearer " + changed.json()["access_token"])
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
    stale_revision = requirement["revision"]
    assigned = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        headers=headers,
        json={"owner_id": user_id, "priority": "P1", "revision": stale_revision},
    )
    assert assigned.status_code == 200, assigned.text
    requirement = assigned.json()
    stale = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        headers=admin_headers,
        json={"priority": "P3", "revision": stale_revision},
    )
    assert stale.status_code == 409 and stale.json()["code"] == 40910
    assert stale.json()["data"]["current_updated_by"] == user_id

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
    for status in ("DEVELOPING", "TESTING"):
        response = client.patch(
            f"/api/v1/requirements/{requirement['id']}/status",
            headers=headers,
            json={"status": status, "revision": current_requirement["revision"]},
        )
        assert response.status_code == 200, response.text
        current_requirement = response.json()

    with Session(engine) as db:
        developer_role = db.scalar(select(Role).where(Role.code == "DEVELOPER"))
        if db.get(UserRole, (user_id, developer_role.id)) is None:
            db.add(UserRole(user_id=user_id, role_id=developer_role.id))
            db.commit()
    roster = client.patch(
        f"/api/v1/requirements/{requirement['id']}/collaborators",
        headers=headers,
        json={
            "kind": "DEVELOPMENT",
            "revision": current_requirement["revision"],
            "user_ids": [user_id],
        },
    )
    assert roster.status_code == 200, roster.text
    completed = client.post(
        f"/api/v1/requirements/{requirement['id']}/development-completion",
        headers=headers,
        json={"revision": roster.json()["revision"]},
    )
    assert completed.status_code == 200, completed.text

    response = client.patch(
        f"/api/v1/requirements/{requirement['id']}/status",
        headers=headers,
        json={"status": "DONE", "revision": completed.json()["revision"]},
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
    notification = client.get("/api/v1/notifications", headers=headers)
    assert notification.status_code == 200
    assert any(n["entity_id"] == feedback["id"] for n in notification.json())


def test_mysql_concurrent_publish(mysql_api):
    client, engine, user_id, headers = mysql_api
    _publish_race(client, (engine, user_id, headers))


def test_mysql_auth_refresh_logout_first_password_and_permissions(mysql_api):
    client, engine, user_id, headers = mysql_api
    with Session(engine) as session:
        user = session.get(User, user_id)
        user.must_change_password = True
        session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"username": "test-admin", "password": "Fresh-test-password-57!"}
    )
    assert login.status_code == 200, login.text
    pair = login.json()
    initial = {"Authorization": "Bearer " + pair["access_token"]}
    assert client.get("/api/v1/feedbacks", headers=initial).status_code == 403
    change = client.post(
        "/api/v1/auth/change-password",
        headers=initial,
        json={
            "current_password": "Fresh-test-password-57!",
            "new_password": "Different-fresh-password-57!",
        },
    )
    assert change.status_code == 200, change.text
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 401
    )
    current = change.json()
    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": current["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": current["refresh_token"]}
        ).status_code
        == 401
    )
    fresh = refreshed.json()
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": fresh["refresh_token"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": fresh["refresh_token"]}
        ).status_code
        == 401
    )
    assert client.get("/api/v1/feedbacks").status_code == 401
    # Create and grant a new role/user through protected HTTP APIs (15-step acceptance).
    role = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "code": "MYSQL_SELF",
            "name": "仅本人",
            "data_scope": "SELF",
            "permission_ids": [
                p["id"]
                for p in client.get("/api/v1/roles/permissions", headers=headers).json()
                if p["code"] in {"rd.feedback.view", "rd.feedback.create", "sys.file.download"}
            ],
        },
    )
    assert role.status_code == 200, role.text
    user = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "mysql-member",
            "display_name": "成员",
            "password": "New-member-password-57!",
            "role_ids": [role.json()["id"]],
        },
    )
    assert user.status_code == 200, user.text
    member_id = user.json()["id"]
    with Session(engine) as session:
        member = session.get(User, member_id)
        member.must_change_password = False
        session.commit()
    member_headers = {"Authorization": f"Bearer {create_access_token(member_id)}"}
    assert client.get("/api/v1/users", headers=member_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/roles",
            headers=member_headers,
            json={"code": "ESCAPE", "name": "非法", "data_scope": "ALL"},
        ).status_code
        == 403
    )
    feedback = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "私人反馈",
            "feedback_type": "SYSTEM_ISSUE",
            "urgency": "NORMAL",
            "description": "scope",
        },
    )
    assert feedback.status_code == 200, feedback.text
    assert (
        client.get(f"/api/v1/feedbacks/{feedback.json()['id']}", headers=member_headers).status_code
        == 404
    )
    assert client.get("/api/v1/feedbacks", headers=member_headers).json()["total"] == 0
    upload = client.post(
        "/api/v1/files",
        headers=headers,
        files={"file": ("private.txt", b"scope-controlled", "text/plain")},
    )
    assert upload.status_code == 200
    assert (
        client.get(
            f"/api/v1/files/{upload.json()['id']}/download", headers=member_headers
        ).status_code
        == 404
    )
    attachment = client.post(
        f"/api/v1/feedbacks/{feedback.json()['id']}/attachments",
        headers=headers,
        files={"file": ("linked.txt", b"linked scope", "text/plain")},
    )
    assert attachment.status_code == 200
    assert (
        client.get(
            f"/api/v1/feedbacks/{feedback.json()['id']}/attachments/{attachment.json()['file_id']}/download",
            headers=member_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/files/{attachment.json()['file_id']}", headers=headers).status_code
        == 409
    )
    logged_member = client.post(
        "/api/v1/auth/login",
        json={"username": "mysql-member", "password": "New-member-password-57!"},
    )
    assert logged_member.status_code == 200
    member_pair = logged_member.json()
    current_member = client.get(f"/api/v1/users/{member_id}", headers=headers).json()
    disabled = client.patch(
        f"/api/v1/users/{member_id}/status",
        headers=headers,
        json={"status": "DISABLED", "revision": current_member["revision"]},
    )
    assert disabled.status_code == 200, disabled.text
    assert (
        client.get(
            "/api/v1/auth/me",
            headers=RedactedHeaders(Authorization="Bearer " + member_pair["access_token"]),
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": member_pair["refresh_token"]}
        ).status_code
        == 401
    )


def test_mysql_catalog_chinese_search_revision_and_files(mysql_api):
    client, _engine, _user_id, headers = mysql_api
    system = client.post(
        "/api/v1/systems", headers=headers, json={"code": "MYSQL57", "name": "中文系统"}
    )
    assert system.status_code == 201, system.text
    sid = system.json()["id"]
    module = client.post(
        f"/api/v1/systems/{sid}/modules",
        headers=headers,
        json={"code": "FEEDBACK", "name": "反馈模块"},
    )
    assert module.status_code == 201, module.text
    feedback = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "中文检索 ABC %_",
            "feedback_type": "SYSTEM_ISSUE",
            "urgency": "NORMAL",
            "description": "中文内容",
            "system_id": sid,
            "module_id": module.json()["id"],
        },
    )
    assert feedback.status_code == 200, feedback.text
    item = feedback.json()
    fid = item["id"]
    assert datetime.fromisoformat(item["created_at"]).tzinfo is not None
    for keyword in ["中文", "abc", "%_"]:
        found = client.get("/api/v1/feedbacks", headers=headers, params={"keyword": keyword})
        assert found.status_code == 200, found.text
        assert found.json()["total"] == 1
    update = client.patch(
        f"/api/v1/feedbacks/{fid}",
        headers=headers,
        json={"title": "修改", "revision": item["revision"]},
    )
    assert update.status_code == 200, update.text
    stale = client.patch(
        f"/api/v1/feedbacks/{fid}",
        headers=headers,
        json={"title": "覆盖", "revision": item["revision"]},
    )
    assert stale.status_code == 409 and stale.json()["code"] == 40910
    illegal = client.patch(
        f"/api/v1/feedbacks/{fid}/status",
        headers=headers,
        json={"status": "ONLINE", "revision": update.json()["revision"]},
    )
    assert illegal.status_code == 422
    upload = client.post(
        "/api/v1/files",
        headers=headers,
        files={"file": ("中文.txt", "附件内容".encode(), "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["id"]
    assert "storage_key" not in upload.json()
    assert (
        client.get(f"/api/v1/files/{file_id}/download", headers=headers).content
        == "附件内容".encode()
    )
    assert client.get(f"/api/v1/files/{file_id}/download").status_code == 401
    assert client.delete(f"/api/v1/files/{file_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/files/{file_id}/download", headers=headers).status_code == 404


def test_mysql_many_feedbacks_and_move_history(mysql_api):
    client, engine, _user_id, headers = mysql_api
    feedbacks = []
    requirement = None
    for i in range(2):
        response = client.post(
            "/api/v1/feedbacks",
            headers=headers,
            json={
                "title": f"归并{i}",
                "feedback_type": "SYSTEM_ISSUE",
                "urgency": "NORMAL",
                "description": "merge",
            },
        )
        assert response.status_code == 200, response.text
        f = response.json()
        feedbacks.append(f)
        payload = (
            {
                "type": "CREATE_NEW",
                "revision": f["revision"],
                "requirement_title": "归并需求",
                "requirement_type": "FEATURE",
                "priority": "P2",
                "description": "merged",
            }
            if requirement is None
            else {
                "type": "LINK_EXISTING",
                "revision": f["revision"],
                "requirement_id": requirement["id"],
            }
        )
        converted = client.post(
            f"/api/v1/feedbacks/{f['id']}/convert", headers=headers, json=payload
        )
        assert converted.status_code == 200, converted.text
        requirement = converted.json()
    versions = []
    for i in range(3):
        response = client.post(
            "/api/v1/versions",
            headers=headers,
            json={"version_no": f"MOVE-{i}", "name": f"版本{i}"},
        )
        assert response.status_code == 200, response.text
        versions.append(response.json())
    attached = client.post(
        f"/api/v1/versions/{versions[0]['id']}/requirements",
        headers=headers,
        json={
            "requirement_id": requirement["id"],
            "revision": requirement["revision"],
            "version_revision": versions[0]["revision"],
        },
    )
    assert attached.status_code == 200, attached.text
    for target in versions[1:]:
        current = client.get(f"/api/v1/requirements/{requirement['id']}", headers=headers).json()
        moved = client.post(
            f"/api/v1/versions/{target['id']}/requirements/move",
            headers=headers,
            json={
                "requirement_id": requirement["id"],
                "revision": current["revision"],
                "version_revision": target["revision"],
                "reason": "迁移保留历史",
            },
        )
        assert moved.status_code == 200, moved.text
    with Session(engine) as session:
        assert session.get(Requirement, requirement["id"]).current_version_id == versions[-1]["id"]
        assert (
            session.scalar(
                select(func.count(VersionRequirement.id)).where(
                    VersionRequirement.requirement_id == requirement["id"],
                    VersionRequirement.active.is_(False),
                )
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count(RequirementFeedback.id)).where(
                    RequirementFeedback.requirement_id == requirement["id"]
                )
            )
            == 2
        )


# Reuse the existing date acceptance matrix against the real MySQL migration.


@pytest.fixture
def postgres_e2e_engine(mysql_api):
    _, engine, user_id, headers = mysql_api
    return engine, user_id, headers


@pytest.fixture
def postgres_http_client(mysql_api):
    return mysql_api[0]


def ready(mysql_api):
    from test_publish_api import _seed_ready_version

    with Session(mysql_api[1]) as session:
        return _seed_ready_version(session, mysql_api[2])


def test_mysql_publish_rolls_back_after_all_business_updates(mysql_api, monkeypatch):
    from app.services.audit_service import AuditService

    client, engine, _, headers = mysql_api
    ids = ready(mysql_api)
    original = AuditService.log

    def fail_after_updates(self, entity_type, entity_id, action, **kwargs):
        if action == "RELEASE_CREATE":
            raise RuntimeError("injected publish failure after all business writes")
        return original(self, entity_type, entity_id, action, **kwargs)

    monkeypatch.setattr(AuditService, "log", fail_after_updates)
    response = client.post(
        f"/api/v1/versions/{ids['version']}/publish",
        headers=headers,
        json={
            "revision": 1,
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": "rollback",
        },
    )
    assert response.status_code == 500
    with Session(engine) as session:
        assert session.get(Version, ids["version"]).status == "READY"
        assert session.get(Requirement, ids["requirement"]).status == "DONE"
        assert session.get(Feedback, ids["feedback"]).status == "REQUIREMENT_LINKED"
        for model in (Version, Requirement, Feedback):
            assert session.get(model, ids[model.__name__.lower()]).revision == 1
        for model in (Release, Notification, OperationLog):
            assert session.scalar(select(func.count(model.id))) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE sys_user SET status='INVALID'",
        "UPDATE IGNORE sys_user SET status='INVALID'",
        "UPDATE sys_user SET status='active'",
        "UPDATE sys_user SET must_change_password=2",
        "UPDATE rd_version_requirement SET active=2",
        "UPDATE rd_requirement_feedback SET is_primary=-1",
        "UPDATE rd_requirement SET current_version_id=999",
        "UPDATE rd_feedback SET main_requirement_id=999",
        "UPDATE rd_version_requirement SET active_requirement_id=NULL",
        "DELETE FROM rd_requirement WHERE id=1",
        "DELETE FROM rd_version WHERE id=1",
    ],
)
def test_mysql_database_domain_and_pointer_bypasses(mysql_api, statement):
    from sqlalchemy.exc import DBAPIError

    ready(mysql_api)
    with mysql_api[1].connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(text(statement))
        connection.rollback()
    with Session(mysql_api[1]) as session:
        assert session.get(Requirement, 1).current_version_id == 1
        assert session.get(Feedback, 1).main_requirement_id == 1


def test_mysql_identifier_equality_matches_postgres(mysql_api):
    _, engine, _, _ = mysql_api
    with Session(engine) as session:
        for username in ("Exact", "exact", "Exact "):
            session.add(
                User(
                    username=username,
                    display_name=username,
                    password_hash="unused",
                    must_change_password=False,
                )
            )
        session.commit()
        for username in ("Exact", "exact", "Exact "):
            found = session.scalar(select(User).where(User.username == username))
            assert found.username == username
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT COUNT(*) FROM sys_user WHERE username=X'4578616374'"))
            == 1
        )


def test_mysql_concurrent_feedback_conversion(mysql_api):
    client, engine, _user_id, headers = mysql_api
    response = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "并发转换",
            "feedback_type": "SYSTEM_ISSUE",
            "urgency": "NORMAL",
            "description": "race",
        },
    )
    assert response.status_code == 200
    f = response.json()
    barrier = Barrier(2)

    def worker(_):
        with TestClient(app) as c:
            barrier.wait(timeout=10)
            return c.post(
                f"/api/v1/feedbacks/{f['id']}/convert",
                headers=headers,
                json={
                    "type": "CREATE_NEW",
                    "revision": f["revision"],
                    "requirement_title": "竞态需求",
                    "requirement_type": "FEATURE",
                    "priority": "P2",
                    "description": "race",
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, range(2))) == [200, 409]
    with Session(engine) as session:
        assert session.scalar(select(func.count(Requirement.id))) == 1
        assert session.scalar(select(func.count(RequirementFeedback.id))) == 1
        assert (
            session.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "CONVERT_REQUIREMENT"
                )
            )
            == 1
        )


def test_mysql_concurrent_migration_preserves_history(mysql_api):
    _client, engine, _user_id, headers = mysql_api
    ids = ready(mysql_api)
    with Session(engine) as session:
        version = session.get(Version, ids["version"])
        version.status = "PLANNING"
        session.add_all(
            [Version(version_no="T1", name="target 1"), Version(version_no="T2", name="target 2")]
        )
        session.commit()
    barrier = Barrier(2)

    def worker(target):
        with TestClient(app) as c:
            barrier.wait(timeout=10)
            return c.post(
                f"/api/v1/versions/{target}/requirements/move",
                headers=headers,
                json={
                    "requirement_id": ids["requirement"],
                    "revision": 1,
                    "version_revision": 1,
                    "reason": "concurrent move",
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, [2, 3])) == [200, 409]
    with Session(engine) as session:
        req = session.get(Requirement, ids["requirement"])
        assert req.revision == 2 and req.current_version_id in (2, 3)
        assert (
            session.scalar(
                select(func.count(VersionRequirement.id)).where(VersionRequirement.active.is_(True))
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count(VersionRequirement.id)).where(
                    VersionRequirement.active.is_(False)
                )
            )
            == 1
        )


test_mysql_date_bounds = _date_bounds
test_mysql_date_validation = _date_validation


@pytest.mark.parametrize("flag", ["foreign_key_checks", "unique_checks"])
@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE sys_user SET revision=revision+1 WHERE id=1",
        "DELETE FROM rd_requirement WHERE id=1",
        "INSERT INTO rd_version_requirement (version_id,requirement_id,active,added_at) "
        "VALUES (999,999,1,UTC_TIMESTAMP(6))",
    ],
)
def test_mysql_cannot_disable_integrity_in_writer_session(mysql_api, flag, mutation):
    from sqlalchemy.exc import DBAPIError

    ready(mysql_api)
    with mysql_api[1].connect() as connection:
        connection.execute(text(f"SET SESSION {flag}=0"))
        with pytest.raises(DBAPIError) as error:
            connection.execute(text(mutation))
        assert error.value.orig.args[0] == 1644
        connection.rollback()
        connection.execute(text(f"SET SESSION {flag}=1"))
    with Session(mysql_api[1]) as session:
        assert session.get(Requirement, 1).current_version_id == 1
        assert session.get(Feedback, 1).main_requirement_id == 1


def test_mysql_restart_and_isolated_backup_restore(mysql_api, monkeypatch, tmp_path):
    import hashlib
    import json
    import shutil
    import subprocess
    import time

    from sqlalchemy.exc import SQLAlchemyError

    from app.core.mysql_preflight import validate_mysql

    client, engine, _, headers = mysql_api
    ids = ready(mysql_api)
    with Session(engine) as db:
        developer = db.scalar(select(Role).where(Role.code == "DEVELOPER"))
        db.add(UserRole(user_id=mysql_api[2], role_id=developer.id))
        designer = db.scalar(select(Role).where(Role.code == "DESIGNER"))
        db.add(UserRole(user_id=mysql_api[2], role_id=designer.id))
        db.get(
            RequirementParticipant, (ids["requirement"], mysql_api[2], "DEVELOPMENT")
        ).completed_at = None
        db.commit()
    current = client.get(f"/api/v1/requirements/{ids['requirement']}", headers=headers).json()
    assigned = client.put(
        f"/api/v1/requirements/{ids['requirement']}/collaborators",
        headers=headers,
        json={
            "revision": current["revision"],
            "owner_id": mysql_api[2],
            "developer_ids": [mysql_api[2]],
            "designer_ids": [],
        },
    )
    assert assigned.status_code == 200, assigned.text
    confirmation = client.post(
        f"/api/v1/requirements/{ids['requirement']}/development-completion",
        headers=headers,
        json={"revision": assigned.json()["revision"]},
    )
    assert confirmation.status_code == 200, confirmation.text
    saved_confirmation = confirmation.json()["development_completions"][0]["completed_at"]
    design = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "title": "设计阶段备份恢复需求",
            "requirement_type": "FEATURE",
            "description": "独立恢复验收",
        },
    ).json()
    for state in ("CONFIRMED", "PLANNED"):
        result = client.patch(
            f"/api/v1/requirements/{design['id']}/status",
            headers=headers,
            json={"revision": design["revision"], "status": state},
        )
        assert result.status_code == 200, result.text
        design = result.json()
    result = client.post(
        f"/api/v1/requirements/{design['id']}/start-stage",
        headers=headers,
        json={"revision": design["revision"], "status": "DESIGNING", "user_ids": [mysql_api[2]]},
    )
    assert result.status_code == 200, result.text
    design = result.json()
    upload = client.post(
        f"/api/v1/feedbacks/{ids['feedback']}/attachments",
        headers=headers,
        files={"file": ("restore.txt", b"isolated mysql57 backup attachment", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    file_id = upload.json()["file_id"]
    source = engine.url.database
    assert (
        source.startswith("iterflow_mysql57_")
        and source.removeprefix("iterflow_mysql57_").isalnum()
    )
    container = TEST_CONTAINER
    inspect_info = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]
    assert inspect_info["Config"]["Image"] == "mysql:5.7.44"
    assert inspect_info["Config"]["Labels"]["com.docker.compose.project"] == TEST_PROJECT
    dump = subprocess.check_output(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-c",
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction '
            "--routines --triggers --hex-blob --set-gtid-purged=OFF " + source,
        ]
    )
    dump_path = tmp_path / "source.sql"
    dump_path.write_bytes(dump)
    dump_path.chmod(0o600)
    source_storage = get_settings().local_storage_root
    saved_storage = tmp_path / "storage-backup"
    shutil.copytree(source_storage, saved_storage)
    for _restart_attempt in range(3):
        subprocess.run(["docker", "restart", container], check=True, stdout=subprocess.DEVNULL)
        engine.dispose()
        for attempt in range(60):
            try:
                with engine.connect() as connection:
                    validate_mysql(connection)
                break
            except SQLAlchemyError:
                if attempt == 59:
                    raise
                time.sleep(0.5)
        assert (
            client.get(f"/api/v1/requirements/{ids['requirement']}", headers=headers).json()[
                "current_version_id"
            ]
            == ids["version"]
        )
        download = f"/api/v1/feedbacks/{ids['feedback']}/attachments/{file_id}/download"
    assert client.get(download, headers=headers).content == b"isolated mysql57 backup attachment"
    restored = source + "_restore"
    restore_storage = tmp_path / "restored-uploads"
    with engine.connect() as connection:
        connection.execute(
            text(f"CREATE DATABASE `{restored}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        )
    restore_engine = create_engine(engine.url.set(database=restored), pool_pre_ping=True)
    event.listen(restore_engine, "connect", database.configure_mysql)
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                container,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot ' + restored,
            ],
            input=dump,
            check=True,
        )
        shutil.copytree(saved_storage, restore_storage)
        with restore_engine.connect() as connection:
            validate_mysql(connection)
        with Session(restore_engine) as session:
            assert session.get(Requirement, ids["requirement"]).current_version_id == ids["version"]
            assert session.get(Feedback, ids["feedback"]).main_requirement_id == ids["requirement"]
            assert session.scalar(select(func.count(User.id))) == 1
            assert session.scalar(select(func.count(VersionRequirement.id))) == 1
            assert session.scalar(select(func.count()).select_from(RequirementParticipant)) == 2
            participant = session.scalar(select(RequirementParticipant))
            assert participant.user_id == mysql_api[2] and participant.discipline == "DEVELOPMENT"
            assert participant.completed_at is not None
            assert participant.completed_at.isoformat().replace("+00:00", "Z") == saved_confirmation
            assert session.get(Requirement, design["id"]).status == "DESIGNING"
            assert (
                session.get(RequirementParticipant, (design["id"], mysql_api[2], "DESIGN"))
                is not None
            )
        monkeypatch.setattr(
            database,
            "SessionLocal",
            sessionmaker(bind=restore_engine, autoflush=False, expire_on_commit=False),
        )
        monkeypatch.setenv("LOCAL_STORAGE_PATH", str(restore_storage))
        get_settings.cache_clear()
        assert (
            client.get(download, headers=headers).content == b"isolated mysql57 backup attachment"
        )
        stage_after_restore = client.post(
            f"/api/v1/requirements/{design['id']}/start-stage",
            headers=headers,
            json={
                "revision": design["revision"],
                "status": "DEVELOPING",
                "user_ids": [mysql_api[2]],
            },
        )
        assert stage_after_restore.status_code == 200, stage_after_restore.text
        assert stage_after_restore.json()["status"] == "DEVELOPING"
        after_restore = client.post(
            "/api/v1/files",
            headers=headers,
            files={"file": ("after-restore.txt", b"restored function writes", "text/plain")},
        )
        assert after_restore.status_code == 200, after_restore.text
        assert (
            client.delete(
                f"/api/v1/files/{after_restore.json()['id']}", headers=headers
            ).status_code
            == 204
        )
        post_dump = subprocess.check_output(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction '
                "--routines --triggers --hex-blob --set-gtid-purged=OFF " + restored,
            ]
        )
        evidence = BACKEND.parent / "docs/evidence/development-completion"
        evidence.mkdir(parents=True, exist_ok=True)
        (
            evidence / ("backup-restore.json" if PORTABLE else "standard-backup-restore.json")
        ).write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "scope": "isolated local synthetic database and storage only",
                    "mysql_version": TEST_VERSION,
                    "source_database": source,
                    "restore_database": restored,
                    "pre_backup_sha256": hashlib.sha256(dump).hexdigest(),
                    "post_backup_sha256": hashlib.sha256(post_dump).hexdigest(),
                    "storage_sha256": hashlib.sha256(
                        b"isolated mysql57 backup attachment"
                    ).hexdigest(),
                    "restart_persistence": True,
                    "successful_consecutive_restarts": 3,
                    "restored_guard_triggers": 73,
                    "profile": TEST_PROJECT,
                    "restored_function_upload": True,
                    "design_state_and_roster_restored": True,
                    "developer_completion_restored": True,
                    "stage_transition_after_restore": True,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        restore_engine.dispose()
        with engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE `{restored}`"))


def test_mysql_preflight_requires_empty_or_verified_schema(mysql_api):
    from app.core.mysql_preflight import validate_mysql

    with mysql_api[1].connect() as connection:
        result = validate_mysql(connection)
        assert result["table_count"] == 24
        with pytest.raises(RuntimeError, match="empty"):
            validate_mysql(connection, empty=True)
        connection.execute(text("DROP TRIGGER domain_sys_user_insert"))
        with pytest.raises(RuntimeError, match="triggers"):
            validate_mysql(connection)
        # Runtime intentionally needs no TRIGGER privilege; migration preflight
        # proves installed guards, runtime principals cannot drop them.
        assert validate_mysql(connection, inspect_triggers=False)["version"] == TEST_VERSION


def test_mysql_real_deadlock_and_lock_timeout_are_conflicts(mysql_api):
    from sqlalchemy.exc import OperationalError

    from app.core.exceptions import ConflictError

    with Session(mysql_api[1]) as session:
        session.add(
            User(
                username="lock-other",
                display_name="other",
                password_hash="unused",
                must_change_password=False,
            )
        )
        session.commit()
    barrier = Barrier(2)

    def worker(first):
        with mysql_api[1].connect() as connection:
            try:
                connection.execute(
                    text("UPDATE sys_user SET revision=revision+1 WHERE id=:id"), {"id": first}
                )
                barrier.wait(timeout=10)
                connection.execute(
                    text("UPDATE sys_user SET revision=revision+1 WHERE id=:id"), {"id": 3 - first}
                )
                connection.commit()
                return "committed", None
            except OperationalError as error:
                connection.rollback()
                return "rejected", error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [1, 2]))
    assert sorted(status for status, _ in results) == ["committed", "rejected"]
    errors = [error for _, error in results if error is not None]
    assert errors[0].orig.args[0] == 1213
    with mysql_api[1].connect() as blocker, mysql_api[1].connect() as waiter:
        blocker.execute(text("UPDATE sys_user SET revision=revision+1 WHERE id=1"))
        waiter.execute(text("SET SESSION innodb_lock_wait_timeout=1"))
        with pytest.raises(OperationalError) as timeout:
            waiter.execute(text("UPDATE sys_user SET revision=revision+1 WHERE id=1"))
        assert timeout.value.orig.args[0] == 1205
        waiter.rollback()
        blocker.rollback()
        errors.append(timeout.value)
    for error in errors:
        generator = database.get_db()
        next(generator)
        with pytest.raises(ConflictError) as mapped:
            generator.throw(error)
        assert mapped.value.status_code == 409 and mapped.value.code == 40940
    with Session(mysql_api[1]) as session:
        assert session.get(User, 1).revision == 2
        assert session.get(User, 2).revision == 2


def test_mysql_runtime_principal_cannot_remove_database_protection(mysql_api, monkeypatch):
    import secrets

    from sqlalchemy.exc import DBAPIError

    from app.core.mysql_preflight import validate_mysql

    client, engine, _, headers = mysql_api
    username = "iterflow_rt_" + uuid4().hex[:12]
    password = secrets.token_hex(24)
    with engine.connect() as connection:
        connection.execute(
            text("CREATE USER :username@'%' IDENTIFIED BY :password"),
            {"username": username, "password": password},
        )
        for table in database.Base.metadata.tables:
            connection.execute(
                text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON `{engine.url.database}`.`{table}` "
                    "TO :username@'%'"
                ),
                {"username": username},
            )
        connection.execute(
            text(f"GRANT SELECT ON `{engine.url.database}`.alembic_version TO :username@'%'"),
            {"username": username},
        )
        connection.execute(
            text(
                f"GRANT SELECT ON `{engine.url.database}`.iterflow_file_key_node TO :username@'%'"
            ),
            {"username": username},
        )
    runtime = create_engine(
        engine.url.set(username=username, password=password), pool_pre_ping=True
    )
    event.listen(runtime, "connect", database.configure_mysql)
    try:
        with runtime.connect() as connection:
            assert validate_mysql(connection, inspect_triggers=False)["table_count"] == 24
            with pytest.raises(DBAPIError):
                connection.execute(text("DROP TRIGGER domain_sys_user_insert"))
            with pytest.raises(DBAPIError):
                connection.execute(text("TRUNCATE TABLE rd_version_requirement"))
            connection.execute(text("SET foreign_key_checks=0"))
            with pytest.raises(DBAPIError) as error:
                connection.execute(text("UPDATE sys_user SET revision=revision+1 WHERE id=1"))
            assert error.value.orig.args[0] == 1644
            connection.execute(text("SET foreign_key_checks=1"))
        monkeypatch.setattr(
            database,
            "SessionLocal",
            sessionmaker(bind=runtime, autoflush=False, expire_on_commit=False),
        )
        response = client.post(
            "/api/v1/feedbacks",
            headers=headers,
            json={
                "title": "least privilege",
                "feedback_type": "SYSTEM_ISSUE",
                "urgency": "NORMAL",
                "description": "runtime account verified",
            },
        )
        assert response.status_code == 200, response.text
        uploaded = client.post(
            f"/api/v1/feedbacks/{response.json()['id']}/attachments",
            headers=headers,
            files={"file": ("runtime.txt", b"definer writes the key registry", "text/plain")},
        )
        assert uploaded.status_code == 200, uploaded.text
        with runtime.connect() as connection:
            with pytest.raises(DBAPIError):
                connection.execute(
                    text("UPDATE iterflow_file_key_node SET segment=X'61' WHERE id=1")
                )
            with pytest.raises(DBAPIError):
                connection.execute(text("SELECT iterflow_register_file_key(X'61')"))
        assert client.get("/api/v1/dashboard/overview", headers=headers).status_code == 200
        with engine.connect() as connection:
            validate_mysql(connection)
    finally:
        runtime.dispose()
        with engine.connect() as connection:
            connection.execute(text("DROP USER :username@'%'"), {"username": username})


def test_mysql_session_strict_mode_without_global_change(mysql_api):
    from app.core.mysql_preflight import validate_mysql

    with mysql_api[1].connect() as connection:
        assert connection.scalar(text("SELECT @@SESSION.innodb_strict_mode")) == 1
        assert connection.scalar(text("SELECT @@SESSION.time_zone")) == "+00:00"
        if PORTABLE:
            assert connection.execute(
                text("SELECT @@GLOBAL.innodb_large_prefix, @@GLOBAL.innodb_strict_mode")
            ).one() == (0, 0)
        connection.execute(text("SET SESSION innodb_strict_mode=OFF"))
        with pytest.raises(RuntimeError, match="innodb_strict_mode"):
            validate_mysql(connection)
        connection.execute(text("SET SESSION innodb_strict_mode=ON"))


def test_mysql_portable_complete_file_key_semantics(mysql_api):
    from sqlalchemy.exc import IntegrityError

    from app.models.entities import FileObject

    engine = mysql_api[1]
    keys = [
        "",
        "Exact",
        "exact",
        "Exact ",
        "😀" * 499 + "甲",
        "😀" * 499 + "乙",
        "😀" * 128,
        "😀" * 128 + "a",
        "a" * 499 + "x",
        "a" * 499 + "y",
    ]
    with Session(engine) as session:
        for key in keys:
            session.add(
                FileObject(
                    storage_key=key,
                    original_name="键",
                    mime_type="text/plain",
                    size=1,
                    sha256="a" * 64,
                    storage_driver="LOCAL",
                )
            )
        session.commit()
        assert set(session.scalars(select(FileObject.storage_key))) == set(keys)
        for key in keys:
            session.add(
                FileObject(
                    storage_key=key,
                    original_name="重复",
                    mime_type="text/plain",
                    size=1,
                    sha256="b" * 64,
                    storage_driver="LOCAL",
                )
            )
            with pytest.raises(IntegrityError) as error:
                session.commit()
            assert error.value.orig.args[0] == 1062
            session.rollback()
        original = session.scalar(select(FileObject).where(FileObject.storage_key == keys[4]))
        original.storage_key = keys[5]
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert original.storage_key == keys[4]
        original.storage_key = "😀" * 499 + "新"
        session.commit()
        session.delete(original)
        session.commit()
        # Deletion frees file uniqueness; the immutable index nodes can be reused.
        session.add(
            FileObject(
                storage_key="😀" * 499 + "新",
                original_name="复用",
                mime_type="text/plain",
                size=1,
                sha256="c" * 64,
                storage_driver="LOCAL",
            )
        )
        session.commit()


def test_mysql_registry_is_exact_and_immutable(mysql_api):
    from sqlalchemy.exc import DBAPIError

    with mysql_api[1].connect() as connection:
        for statement in (
            "UPDATE iterflow_file_key_node SET segment=X'61' WHERE id=1",
            "DELETE FROM iterflow_file_key_node WHERE id=1",
            "INSERT INTO iterflow_file_key_node (id,parent_id,segment) VALUES (100,100,X'61')",
        ):
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(statement))
            assert error.value.orig.args[0] == 1644
            connection.rollback()


def test_mysql_raw_permissive_writer_cannot_truncate_file_key(mysql_api):
    from sqlalchemy.exc import DBAPIError

    with mysql_api[1].connect() as connection:
        connection.execute(text("SET SESSION sql_mode=''"))
        with pytest.raises(DBAPIError) as error:
            connection.execute(
                text(
                    "INSERT INTO sys_file(storage_key,original_name,mime_type,size,sha256,"
                    "storage_driver,created_at,updated_at,revision) VALUES "
                    "(:key,'invalid','text/plain',1,REPEAT('a',64),'LOCAL',UTC_TIMESTAMP(6),"
                    "UTC_TIMESTAMP(6),1)"
                ),
                {"key": ("😀" * 501).encode()},
            )
        assert error.value.orig.args[0] == 1644
        connection.rollback()
        assert connection.scalar(text("SELECT COUNT(*) FROM sys_file")) == 0


def test_mysql_upgrade_legacy_0001_preserves_full_keys(monkeypatch):
    """Separate old-ON test database; never change either running server's globals."""
    from app.cli import migrate
    from app.core.mysql_preflight import validate_mysql
    from app.models.entities import FileObject

    url = make_url(os.environ["DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == TEST_PORT
    admin = create_engine(url.set(port=57357, database="iterflow_mysql57_proof"))
    name = "iterflow_mysql57_legacy_" + uuid4().hex
    with admin.connect() as c:
        assert c.scalar(text("SELECT VERSION()")) == "5.7.44"
        assert c.scalar(text("SELECT @@GLOBAL.innodb_large_prefix")) == 1
        c.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"))
    engine = create_engine(url.set(port=57357, database=name))
    event.listen(engine, "connect", database.configure_mysql)
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(BACKEND / "alembic-mysql.ini")), "mysql57_0001")
        keys = ["😀" * 499 + "甲", "😀" * 499 + "乙", "Exact", "Exact "]
        with Session(engine) as session:
            for key in keys:
                session.add(
                    FileObject(
                        storage_key=key,
                        original_name="legacy",
                        mime_type="text/plain",
                        size=1,
                        sha256="a" * 64,
                        storage_driver="LOCAL",
                    )
                )
            session.commit()
        with engine.connect() as c:
            assert validate_mysql(c, allow_legacy=True)["table_count"] == 22
            with pytest.raises(RuntimeError, match="head"):
                validate_mysql(c)
        monkeypatch.setattr(migrate, "engine", engine)
        migrate.main()
        with engine.connect() as c:
            assert validate_mysql(c)["table_count"] == 24
        with Session(engine) as session:
            assert set(session.scalars(select(FileObject.storage_key))) == set(keys)
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()
        get_settings.cache_clear()

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
from test_v1_e2e_postgres import (
    test_full_v1_business_lifecycle_over_http_and_postgresql as _lifecycle,
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
    User,
    Version,
    VersionRequirement,
)


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def mysql_api(monkeypatch, tmp_path):
    url = make_url(os.environ["DATABASE_URL"])
    assert url.drivername == "mysql+pymysql"
    assert url.host == "127.0.0.1" and url.port == 57357, "local dedicated container only"
    admin = create_engine(url)
    name = "iterflow_mysql57_" + uuid4().hex
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT VERSION()")) == "5.7.44"
        connection.execute(
            text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        )
    test_url = url.set(database=name)
    monkeypatch.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    engine = create_engine(test_url, isolation_level="READ COMMITTED", pool_size=8, max_overflow=4)
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
    client, engine, user_id, headers = mysql_api
    _lifecycle(client, (engine, user_id, headers))


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
        "INSERT INTO rd_version_requirement (version_id,requirement_id,active,added_at) VALUES (999,999,1,UTC_TIMESTAMP(6))",
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

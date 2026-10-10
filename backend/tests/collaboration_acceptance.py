"""Shared HTTP acceptance scenarios run against PostgreSQL and real MySQL 5.7."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Notification, OperationLog, Requirement, RequirementParticipant
from app.services.requirement_collaboration_service import RequirementCollaborationService


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


def setup_team(fixture):
    client, _engine, _, admin = fixture
    roles = {r["code"]: r["id"] for r in client.get("/api/v1/roles", headers=admin).json()}
    people, tokens = {}, {}
    for number, codes in enumerate(
        [["PRODUCT_MANAGER"], ["DEVELOPER"], ["DEVELOPER", "DESIGNER"], ["DESIGNER"], ["MEMBER"]], 1
    ):
        name = f"ceshi{number:03}"
        response = client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "username": name,
                "display_name": ["产品", "开发甲", "开发兼设计", "设计乙", "无关成员"][number - 1],
                "password": "ceshi-init-123",
                "role_ids": [roles[c] for c in codes],
            },
        )
        assert response.status_code == 200, response.text
        people[name] = response.json()["id"]
        pair = client.post(
            "/api/v1/auth/login", json={"username": name, "password": "ceshi-init-123"}
        )
        assert pair.status_code == 200
        initial = {"Authorization": "Bearer " + pair.json()["access_token"]}
        blocked = client.get("/api/v1/requirements", headers=initial)
        assert blocked.status_code == 403
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=initial,
            json={"current_password": "ceshi-init-123", "new_password": "ceshi123"},
        )
        assert changed.status_code == 200, changed.text
        tokens[name] = RedactedHeaders(Authorization="Bearer " + changed.json()["access_token"])
    response = client.post(
        "/api/v1/requirements",
        headers=tokens["ceshi001"],
        json={
            "title": "多角色中文协作需求",
            "requirement_type": "FEATURE",
            "description": "多人开发设计验收",
        },
    )
    assert response.status_code == 200, response.text
    return people, tokens, response.json()


def assign(client, header, req, people):
    return client.put(
        f"/api/v1/requirements/{req['id']}/collaborators",
        headers=header,
        json={
            "revision": req["revision"],
            "owner_id": people["ceshi001"],
            "developer_ids": [people["ceshi002"], people["ceshi003"]],
            "designer_ids": [people["ceshi003"], people["ceshi004"]],
        },
    )


def exercise_assignment_scope_and_notifications(fixture):
    client, engine, _, _ = fixture
    people, tokens, req = setup_team(fixture)
    path = f"/api/v1/requirements/{req['id']}"
    assert client.get(path, headers=tokens["ceshi002"]).status_code == 404
    assert (
        client.get("/api/v1/requirements/assignee-options", headers=tokens["ceshi002"]).status_code
        == 403
    )
    result = assign(client, tokens["ceshi001"], req, people)
    assert result.status_code == 200, result.text
    assert result.json()["revision"] == 2
    assert [u["display_name"] for u in result.json()["developers"]] == ["开发甲", "开发兼设计"]
    options = client.get(
        "/api/v1/requirements/assignee-options",
        headers=tokens["ceshi001"],
        params={"kind": "DESIGNER", "keyword": "设计"},
    ).json()
    assert {u["user_id"] for u in options["items"]} == {people["ceshi003"], people["ceshi004"]}
    assert all(
        set(u) == {"user_id", "display_name", "can_develop", "can_design"} for u in options["items"]
    )
    for name in ["ceshi002", "ceshi003", "ceshi004"]:
        assert client.get(path, headers=tokens[name]).status_code == 200
        assert client.get("/api/v1/requirements", headers=tokens[name]).json()["total"] == 1
        assert client.get(path + "/collaborators", headers=tokens[name]).status_code == 200
        assert client.get("/api/v1/users", headers=tokens[name]).status_code == 403
        assert (
            client.put(
                path + "/collaborators",
                headers=tokens[name],
                json={"revision": 2, "owner_id": None, "developer_ids": [], "designer_ids": []},
            ).status_code
            == 403
        )
    assert client.get(path, headers=tokens["ceshi005"]).status_code == 404
    assert client.get("/api/v1/requirements", headers=tokens["ceshi005"]).json()["total"] == 0
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(RequirementParticipant)) == 4
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(Notification.entity_type == "REQUIREMENT")
            )
            == 3
        )
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi003"]
                )
            )
            == 1
        )
    assert assign(client, tokens["ceshi001"], req, people).status_code == 409
    # A collaborator can update this requirement while other records stay outside their scope.
    changed = client.patch(
        path + "/status", headers=tokens["ceshi002"], json={"revision": 2, "status": "CONFIRMED"}
    )
    assert changed.status_code == 200, changed.text
    with Session(engine) as db:
        assert any(
            "草稿 → 已确认" in content for content in db.scalars(select(Notification.content))
        )
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(Notification.entity_type == "REQUIREMENT")
            )
            == 6
        )
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi002"]
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "ASSIGN_COLLABORATORS"
                )
            )
            == 1
        )
    # Remove all participants: SELF access disappears, including after a prior successful read.
    removed = client.put(
        path + "/collaborators",
        headers=tokens["ceshi001"],
        json={
            "revision": 3,
            "owner_id": people["ceshi001"],
            "developer_ids": [],
            "designer_ids": [],
        },
    )
    assert removed.status_code == 200, removed.text
    assert client.get(path, headers=tokens["ceshi002"]).status_code == 404
    assert (
        client.patch(
            path + "/status", headers=tokens["ceshi002"], json={"revision": 4, "status": "PLANNED"}
        ).status_code
        == 404
    )


def exercise_invalid_and_rollback(fixture, monkeypatch):
    client, engine, _, _ = fixture
    people, tokens, req = setup_team(fixture)
    path = f"/api/v1/requirements/{req['id']}/collaborators"
    for patch in [
        {"developer_ids": [people["ceshi005"]]},
        {"designer_ids": [people["ceshi002"]]},
        {"developer_ids": [people["ceshi002"], people["ceshi002"]]},
        {"owner_id": 999999},
    ]:
        body = {"revision": 1, "owner_id": None, "developer_ids": [], "designer_ids": []} | patch
        assert client.put(path, headers=tokens["ceshi001"], json=body).status_code == 422

    def fail_after_notifications(self, *args):
        original(self, *args)
        raise RuntimeError("injected after notification writes")

    original = RequirementCollaborationService.notify
    monkeypatch.setattr(RequirementCollaborationService, "notify", fail_after_notifications)
    # The real HTTP transaction must roll back every write, not merely avoid commit in a mock.
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as failing:
        response = assign(failing, tokens["ceshi001"], req, people)
        assert response.status_code == 500
    with Session(engine) as db:
        stored = db.get(Requirement, req["id"])
        assert stored.revision == 1 and stored.owner_id is None
        assert db.scalar(select(func.count()).select_from(RequirementParticipant)) == 0
        assert db.scalar(select(func.count(Notification.id))) == 0
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "ASSIGN_COLLABORATORS"
                )
            )
            == 0
        )


def exercise_concurrent_assignment(fixture):
    client, engine, _, admin = fixture
    people, tokens, req = setup_team(fixture)
    barrier = Barrier(2)

    def write(header):
        barrier.wait(timeout=10)
        return assign(client, header, req, people)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [tokens["ceshi001"], admin]))
    assert sorted(r.status_code for r in results) == [200, 409]
    with Session(engine) as db:
        assert db.get(Requirement, req["id"]).revision == 2
        assert db.scalar(select(func.count()).select_from(RequirementParticipant)) == 4
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "ASSIGN_COLLABORATORS"
                )
            )
            == 1
        )
        # Admin winner notifies the total owner too; product winner omits their own notice.
        assert db.scalar(select(func.count(Notification.id))) in (3, 4)


def exercise_publish_and_status_rollback(fixture, monkeypatch):
    client, engine, _, admin = fixture
    people, tokens, req = setup_team(fixture)
    assert assign(client, tokens["ceshi001"], req, people).status_code == 200
    path = f"/api/v1/requirements/{req['id']}"
    original = RequirementCollaborationService.notify

    def fail(self, *args):
        original(self, *args)
        raise RuntimeError("injected notification failure")

    with monkeypatch.context() as patched:
        patched.setattr(RequirementCollaborationService, "notify", fail)
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as failing:
            assert (
                failing.patch(
                    path + "/status",
                    headers=tokens["ceshi002"],
                    json={"revision": 2, "status": "CONFIRMED"},
                ).status_code
                == 500
            )
    with Session(engine) as db:
        stored = db.get(Requirement, req["id"])
        assert stored.revision == 2 and stored.status == "DRAFT"
        assert db.scalar(select(func.count(Notification.id))) == 3
    changed = client.patch(
        path + "/status", headers=tokens["ceshi002"], json={"revision": 2, "status": "CONFIRMED"}
    )
    assert changed.status_code == 200
    version = client.post(
        "/api/v1/versions",
        headers=tokens["ceshi001"],
        json={"version_no": "COLLAB-1", "name": "协作验收"},
    ).json()
    attached = client.post(
        f"/api/v1/versions/{version['id']}/requirements",
        headers=tokens["ceshi001"],
        json={
            "requirement_id": req["id"],
            "revision": 3,
            "version_revision": version["revision"],
        },
    )
    assert attached.status_code == 200, attached.text
    for state in ["DEVELOPING", "TESTING", "DONE"]:
        current = client.get(path, headers=tokens["ceshi002"]).json()
        assert (
            client.patch(
                path + "/status",
                headers=tokens["ceshi002"],
                json={"revision": current["revision"], "status": state},
            ).status_code
            == 200
        )
    vpath = f"/api/v1/versions/{version['id']}"
    for state in ["DEVELOPING", "TESTING", "READY"]:
        current = client.get(vpath, headers=admin).json()
        assert (
            client.patch(
                vpath + "/status",
                headers=admin,
                json={"revision": current["revision"], "status": state},
            ).status_code
            == 200
        )
    current = client.get(vpath, headers=admin).json()
    with Session(engine) as db:
        before = db.scalar(select(func.count(Notification.id)))
    # Fault occurs after the old release/requirement writes and new notification writes.
    with monkeypatch.context() as patched:
        patched.setattr(RequirementCollaborationService, "notify", fail)
        with TestClient(app, raise_server_exceptions=False) as failing:
            failed = failing.post(
                vpath + "/publish",
                headers=admin,
                json={
                    "revision": current["revision"],
                    "release_notes": "回滚注入",
                    "released_at": "2026-10-10T01:00:00Z",
                },
            )
            assert failed.status_code == 500, failed.text
    from app.models.entities import Release, Version

    with Session(engine) as db:
        assert db.get(Requirement, req["id"]).status == "DONE"
        assert db.get(Version, version["id"]).status == "READY"
        assert db.scalar(select(func.count(Release.id))) == 0
        assert db.scalar(select(func.count(Notification.id))) == before
    published = client.post(
        vpath + "/publish",
        headers=admin,
        json={
            "revision": current["revision"],
            "release_notes": "协作上线验收",
            "released_at": "2026-10-10T01:00:00Z",
        },
    )
    assert published.status_code == 200, published.text
    assert client.get(path, headers=tokens["ceshi004"]).json()["status"] == "ONLINE"
    assert (
        client.post(
            vpath + "/publish",
            headers=admin,
            json={
                "revision": current["revision"],
                "release_notes": "重复",
                "released_at": "2026-10-10T01:00:00Z",
            },
        ).status_code
        == 409
    )
    with Session(engine) as db:
        assert db.scalar(select(func.count(Notification.id))) == before + 4
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi003"], Notification.title.like("%已上线")
                )
            )
            == 1
        )


def exercise_role_revocation(fixture):
    client, engine, _, admin = fixture
    people, tokens, req = setup_team(fixture)
    assert assign(client, tokens["ceshi001"], req, people).status_code == 200
    path = f"/api/v1/requirements/{req['id']}"
    assert (
        client.patch(
            f"/api/v1/users/{people['ceshi004']}/status",
            headers=admin,
            json={"revision": 2, "status": "DISABLED"},
        ).status_code
        == 200
    )
    assert client.get(path, headers=tokens["ceshi004"]).status_code == 401
    options = client.get(
        "/api/v1/requirements/assignee-options",
        headers=tokens["ceshi001"],
        params={"kind": "DESIGNER"},
    ).json()
    assert people["ceshi004"] not in {u["user_id"] for u in options["items"]}
    # Existing assignment remains historical until explicitly removed; it grants no login bypass.
    changed = client.patch(
        path + "/status", headers=tokens["ceshi002"], json={"revision": 2, "status": "CONFIRMED"}
    )
    assert changed.status_code == 200
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi004"]
                )
            )
            == 1
        )
    updated = client.put(
        f"/api/v1/users/{people['ceshi003']}/roles",
        headers=admin,
        json={"revision": 2, "role_ids": []},
    )
    assert updated.status_code == 200, updated.text
    assert client.get(path, headers=tokens["ceshi003"]).status_code == 403
    assert (
        client.get(
            "/api/v1/requirements/assignee-options",
            headers=tokens["ceshi001"],
            params={"kind": "DEVELOPER"},
        ).json()["total"]
        == 1
    )


def exercise_database_guards(fixture):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    client, engine, _, _ = fixture
    people, tokens, req = setup_team(fixture)
    assert assign(client, tokens["ceshi001"], req, people).status_code == 200
    bad_statements = [
        ("INSERT INTO rd_requirement_participant VALUES (:req, :user, 'DESIGN ')", 1644, "23514"),
        (
            "INSERT INTO rd_requirement_participant VALUES (:req, :user, 'development')",
            1644,
            "23514",
        ),
        ("INSERT INTO rd_requirement_participant VALUES (:req, 999999, 'DESIGN')", 1452, "23503"),
        (
            "INSERT INTO rd_requirement_participant VALUES (:req, :user, 'DEVELOPMENT')",
            1062,
            "23505",
        ),
    ]
    for statement, mysql_code, pg_code in bad_statements:
        with engine.connect() as db:
            with pytest.raises(DBAPIError) as error:
                db.execute(text(statement), {"req": req["id"], "user": people["ceshi002"]})
            if engine.dialect.name == "mysql":
                assert error.value.orig.args[0] == mysql_code
            else:
                assert error.value.orig.sqlstate == pg_code
            db.rollback()
    if engine.dialect.name == "mysql":
        for flag in ["foreign_key_checks", "unique_checks"]:
            for mutation in [
                "INSERT INTO rd_requirement_participant VALUES (:req,:user,'DESIGN')",
                "UPDATE rd_requirement_participant SET discipline='DESIGN' "
                "WHERE requirement_id=:req AND user_id=:user",
                "DELETE FROM rd_requirement_participant "
                "WHERE requirement_id=:req AND user_id=:user",
            ]:
                with engine.connect() as db:
                    db.execute(text(f"SET SESSION {flag}=0"))
                    try:
                        with pytest.raises(DBAPIError) as error:
                            db.execute(
                                text(mutation), {"req": req["id"], "user": people["ceshi002"]}
                            )
                        assert error.value.orig.args[0] == 1644
                        db.rollback()
                    finally:
                        db.execute(text(f"SET SESSION {flag}=1"))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(RequirementParticipant)) == 4

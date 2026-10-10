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

    def fail_after_notifications(self, *args, **kwargs):
        original(self, *args, **kwargs)
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

    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
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
    for developer in ["ceshi002", "ceshi003"]:
        completed = confirm_member(client, req["id"], tokens[developer])
        assert completed.status_code == 200, completed.text
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
    insert = "INSERT INTO rd_requirement_participant (requirement_id,user_id,discipline) "
    bad_statements = [
        (
            insert + "VALUES (:req, :user, 'DESIGN ')",
            1644,
            "23514",
        ),
        (
            insert + "VALUES (:req, :user, 'development')",
            1644,
            "23514",
        ),
        (
            insert + "VALUES (:req, 999999, 'DESIGN')",
            1452,
            "23503",
        ),
        (
            insert + "VALUES (:req, :user, 'DEVELOPMENT')",
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
                insert + "VALUES (:req,:user,'DESIGN')",
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


def grant_stage_lead(fixture, user_id):
    client, _, _, admin = fixture
    roles = {r["code"]: r["id"] for r in client.get("/api/v1/roles", headers=admin).json()}
    user = client.get(f"/api/v1/users/{user_id}", headers=admin).json()
    result = client.put(
        f"/api/v1/users/{user_id}/roles",
        headers=admin,
        json={
            "revision": user["revision"],
            "role_ids": [roles["PRODUCT_MANAGER"], roles["DEVELOPMENT_LEAD"]],
        },
    )
    assert result.status_code == 200, result.text


def planned_requirement(client, token, req):
    for status in ["CONFIRMED", "PLANNED"]:
        result = client.patch(
            f"/api/v1/requirements/{req['id']}/status",
            headers=token,
            json={"revision": req["revision"], "status": status},
        )
        assert result.status_code == 200, result.text
        req = result.json()
    return req


def exercise_design_stage(fixture):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    client, engine, _, _ = fixture
    people, tokens, req = setup_team(fixture)
    grant_stage_lead(fixture, people["ceshi001"])
    path = f"/api/v1/requirements/{req['id']}"
    assert (
        client.patch(
            path + "/collaborators",
            headers=tokens["ceshi001"],
            json={"revision": 1, "kind": "DESIGN", "user_ids": [people["ceshi004"]]},
        ).status_code
        == 409
    )
    req = planned_requirement(client, tokens["ceshi001"], req)
    payload = {
        "revision": req["revision"],
        "status": "DESIGNING",
        "user_ids": [people["ceshi003"], people["ceshi004"]],
    }
    assert (
        client.patch(
            path + "/status",
            headers=tokens["ceshi001"],
            json={"revision": req["revision"], "status": "DESIGNING"},
        ).status_code
        == 409
    )
    for ids in [[], [people["ceshi002"]], [people["ceshi004"]] * 2, [999999]]:
        assert (
            client.post(
                path + "/start-stage", headers=tokens["ceshi001"], json={**payload, "user_ids": ids}
            ).status_code
            == 422
        )
    started = client.post(path + "/start-stage", headers=tokens["ceshi001"], json=payload)
    assert started.status_code == 200, started.text
    req = started.json()
    assert req["status"] == "DESIGNING" and req["revision"] == 4
    roster = client.get(path + "/collaborators", headers=tokens["ceshi001"]).json()
    assert len(roster["designers"]) == 2 and not roster["developers"]
    assert (
        client.post(path + "/start-stage", headers=tokens["ceshi001"], json=payload).status_code
        == 409
    )
    assert client.get(path, headers=tokens["ceshi004"]).status_code == 200
    assert (
        client.post(
            path + "/start-stage",
            headers=tokens["ceshi004"],
            json={"revision": 4, "status": "DEVELOPING", "user_ids": [people["ceshi002"]]},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            path + "/status",
            headers=tokens["ceshi004"],
            json={"revision": 4, "status": "DEVELOPING"},
        ).status_code
        == 409
    )
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi004"]
                )
            )
            == 1
        )
    developer = client.post(
        path + "/start-stage",
        headers=tokens["ceshi001"],
        json={
            "revision": 4,
            "status": "DEVELOPING",
            "user_ids": [people["ceshi002"], people["ceshi003"]],
        },
    )
    assert developer.status_code == 200, developer.text
    assert developer.json()["revision"] == 5
    roster = client.get(path + "/collaborators", headers=tokens["ceshi001"]).json()
    assert len(roster["designers"]) == 2 and len(roster["developers"]) == 2
    assert (
        client.patch(
            path + "/collaborators",
            headers=tokens["ceshi001"],
            json={"revision": 5, "kind": "DESIGN", "user_ids": [people["ceshi004"]]},
        ).status_code
        == 409
    )
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi004"]
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == people["ceshi002"]
                )
            )
            == 1
        )
    owner_change = client.patch(
        path + "/collaborators",
        headers=tokens["ceshi001"],
        json={"revision": 5, "kind": "OWNER", "owner_id": people["ceshi001"]},
    )
    assert owner_change.status_code == 200, owner_change.text
    assert owner_change.json()["revision"] == 6
    assert len(owner_change.json()["designers"]) == 2
    assert len(owner_change.json()["developers"]) == 2
    assert (
        client.patch(
            path + "/collaborators",
            headers=tokens["ceshi001"],
            json={"revision": 5, "kind": "OWNER", "owner_id": None},
        ).status_code
        == 409
    )
    adjusted = client.patch(
        path + "/collaborators",
        headers=tokens["ceshi001"],
        json={"revision": 6, "kind": "DEVELOPMENT", "user_ids": [people["ceshi003"]]},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert len(adjusted.json()["designers"]) == 2 and len(adjusted.json()["developers"]) == 1
    # Design can be skipped; development participants are still chosen at stage start.
    second = client.post(
        "/api/v1/requirements",
        headers=tokens["ceshi001"],
        json={
            "title": "无需设计的后端需求",
            "requirement_type": "TECH",
            "description": "直接开发",
        },
    ).json()
    second = planned_requirement(client, tokens["ceshi001"], second)
    skip = client.post(
        f"/api/v1/requirements/{second['id']}/start-stage",
        headers=tokens["ceshi001"],
        json={
            "revision": second["revision"],
            "status": "DEVELOPING",
            "user_ids": [people["ceshi002"]],
        },
    )
    assert skip.status_code == 200, skip.text
    assert not client.get(
        f"/api/v1/requirements/{second['id']}/collaborators", headers=tokens["ceshi001"]
    ).json()["designers"]
    # Effective SQL enum checks expanded; all original guards remain enforced.
    with engine.begin() as db:
        db.execute(
            text("UPDATE rd_requirement SET status='DESIGNING' WHERE id=:id"), {"id": req["id"]}
        )
    for statement in ["status='DESIGNING '", "source='BAD'"]:
        with engine.connect() as db:
            with pytest.raises(DBAPIError):
                db.execute(
                    text(f"UPDATE rd_requirement SET {statement} WHERE id=:id"), {"id": req["id"]}
                )
            db.rollback()


def exercise_stage_rollback_and_race(fixture, monkeypatch):
    client, engine, _, _ = fixture
    people, tokens, req = setup_team(fixture)
    grant_stage_lead(fixture, people["ceshi001"])
    req = planned_requirement(client, tokens["ceshi001"], req)
    path = f"/api/v1/requirements/{req['id']}/start-stage"
    payload = {"revision": 3, "status": "DESIGNING", "user_ids": [people["ceshi004"]]}
    original = RequirementCollaborationService.notify

    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("injected after stage and notification writes")

    from fastapi.testclient import TestClient

    from app.main import app

    with monkeypatch.context() as patched:
        patched.setattr(RequirementCollaborationService, "notify", fail)
        with TestClient(app, raise_server_exceptions=False) as no_raise:
            assert no_raise.post(path, headers=tokens["ceshi001"], json=payload).status_code == 500
    with Session(engine) as db:
        saved = db.get(Requirement, req["id"])
        assert saved.status == "PLANNED" and saved.revision == 3
        assert db.scalar(select(func.count()).select_from(RequirementParticipant)) == 0
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(OperationLog.action == "ASSIGN_DESIGN")
            )
            == 0
        )
    barrier = Barrier(2)

    def start(p):
        barrier.wait(timeout=10)
        return client.post(path, headers=tokens["ceshi001"], json=p).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                start,
                [
                    payload,
                    {"revision": 3, "status": "DEVELOPING", "user_ids": [people["ceshi002"]]},
                ],
            )
        )
    assert sorted(outcomes) == [200, 409]
    with Session(engine) as db:
        saved = db.get(Requirement, req["id"])
        assert saved.revision == 4
        kinds = set(db.scalars(select(RequirementParticipant.discipline)))
        assert kinds == ({"DESIGN"} if saved.status == "DESIGNING" else {"DEVELOPMENT"})


def exercise_design_blocks_publish(fixture):
    from app.models.entities import Release, Version

    client, engine, _, admin = fixture
    people, tokens, req = setup_team(fixture)
    grant_stage_lead(fixture, people["ceshi001"])
    version = client.post(
        "/api/v1/versions",
        headers=admin,
        json={"version_no": "DESIGN-BLOCK", "name": "设计不能提前发布"},
    ).json()
    attached = client.post(
        f"/api/v1/versions/{version['id']}/requirements",
        headers=admin,
        json={"requirement_id": req["id"], "revision": 1, "version_revision": 1},
    )
    assert attached.status_code == 200, attached.text
    stage = client.post(
        f"/api/v1/requirements/{req['id']}/start-stage",
        headers=tokens["ceshi001"],
        json={"revision": 2, "status": "DESIGNING", "user_ids": [people["ceshi004"]]},
    )
    assert stage.status_code == 200, stage.text
    # Explicit fixture creates a READY version with an incomplete requirement,
    # proving publish rechecks blockers independently of version status UI.
    with Session(engine) as db:
        db.get(Version, version["id"]).status = "READY"
        db.commit()
    result = client.post(
        f"/api/v1/versions/{version['id']}/publish",
        headers=admin,
        json={
            "revision": 2,
            "released_at": "2026-10-10T10:00:00Z",
            "release_notes": "不能发布设计中需求",
        },
    )
    assert result.status_code == 409, result.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Release)) == 0
        assert db.get(Requirement, req["id"]).status == "DESIGNING"
        assert db.get(Version, version["id"]).status == "READY"


def completion_team(fixture):
    client, _engine, _, admin = fixture
    people, tokens, req = setup_team(fixture)
    grant_stage_lead(fixture, people["ceshi001"])
    version = client.post(
        "/api/v1/versions", headers=admin, json={"version_no": "COMPLETE-1", "name": "全员确认"}
    ).json()
    attached = client.post(
        f"/api/v1/versions/{version['id']}/requirements",
        headers=admin,
        json={
            "requirement_id": req["id"],
            "revision": req["revision"],
            "version_revision": version["revision"],
        },
    )
    assert attached.status_code == 200, attached.text
    req = client.get(f"/api/v1/requirements/{req['id']}", headers=admin).json()
    started = client.post(
        f"/api/v1/requirements/{req['id']}/start-stage",
        headers=tokens["ceshi001"],
        json={
            "revision": req["revision"],
            "status": "DEVELOPING",
            "user_ids": [people["ceshi002"], people["ceshi003"]],
        },
    )
    assert started.status_code == 200, started.text
    for status in ["TESTING", "DONE"]:
        req = client.get(f"/api/v1/requirements/{req['id']}", headers=admin).json()
        result = client.patch(
            f"/api/v1/requirements/{req['id']}/status",
            headers=admin,
            json={"revision": req["revision"], "status": status},
        )
        assert result.status_code == 200, result.text
    for status in ["DEVELOPING", "TESTING", "READY"]:
        version = client.get(f"/api/v1/versions/{version['id']}", headers=admin).json()
        result = client.patch(
            f"/api/v1/versions/{version['id']}/status",
            headers=admin,
            json={"revision": version["revision"], "status": status},
        )
        assert result.status_code == 200, result.text
    return people, tokens, req, version


def confirm_member(client, req_id, headers):
    current = client.get(f"/api/v1/requirements/{req_id}", headers=headers).json()
    return client.post(
        f"/api/v1/requirements/{req_id}/development-completion",
        headers=headers,
        json={"revision": current["revision"]},
    )


def exercise_completion_gate(fixture):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.models.entities import Release, Version

    client, engine, _, admin = fixture
    people, tokens, req, version = completion_team(fixture)
    path = f"/api/v1/requirements/{req['id']}"
    vpath = f"/api/v1/versions/{version['id']}"
    version = client.get(vpath, headers=admin).json()
    body = {
        "revision": version["revision"],
        "released_at": "2026-10-10T10:00:00Z",
        "release_notes": "全员确认门禁",
    }
    for header, expected in [(admin, 403), (tokens["ceshi001"], 403), (tokens["ceshi005"], 403)]:
        current = client.get(path, headers=admin).json()
        assert (
            client.post(
                path + "/development-completion",
                headers=header,
                json={"revision": current["revision"]},
            ).status_code
            == expected
        )
    current = client.get(path, headers=admin).json()
    assert (
        client.post(
            path + "/development-completion",
            headers=tokens["ceshi002"],
            json={"revision": current["revision"], "user_id": people["ceshi003"]},
        ).status_code
        == 422
    )
    blocked = client.post(vpath + "/publish/check", headers=admin)
    assert blocked.status_code == 409
    assert any(
        c["type"] == "DEVELOPMENT_COMPLETION_CHECK" and not c["passed"]
        for c in blocked.json()["data"]["checks"]
    )
    assert client.post(vpath + "/publish", headers=admin, json=body).status_code == 409
    first = confirm_member(client, req["id"], tokens["ceshi002"])
    assert first.status_code == 200, first.text
    values = first.json()["development_completions"]
    assert [v["completed_at"] is not None for v in values] == [True, False]
    assert values[0]["completed_at"].endswith("Z")
    assert confirm_member(client, req["id"], tokens["ceshi002"]).status_code == 409
    assert client.post(vpath + "/publish", headers=admin, json=body).status_code == 409
    assert confirm_member(client, req["id"], tokens["ceshi003"]).status_code == 200
    assert client.post(vpath + "/publish/check", headers=admin).status_code == 200
    # Returning to development invalidates every acknowledgement atomically.
    current = client.get(path, headers=admin).json()
    rework = client.patch(
        path + "/status",
        headers=admin,
        json={"revision": current["revision"], "status": "DEVELOPING", "reason": "返工重新验证"},
    )
    assert rework.status_code == 200, rework.text
    assert all(
        v["completed_at"] is None
        for v in client.get(path + "/collaborators", headers=admin).json()[
            "development_completions"
        ]
    )
    assert confirm_member(client, req["id"], tokens["ceshi002"]).status_code == 200
    # Group and legacy PUT keep confirmations for unchanged members.
    # Removing and readding a developer must not resurrect their confirmation.
    current = client.get(path, headers=admin).json()
    group = client.patch(
        path + "/collaborators",
        headers=admin,
        json={
            "revision": current["revision"],
            "kind": "DEVELOPMENT",
            "user_ids": [people["ceshi002"]],
        },
    )
    assert (
        group.status_code == 200
        and group.json()["development_completions"][0]["completed_at"] is not None
    )
    full = client.put(
        path + "/collaborators",
        headers=admin,
        json={
            "revision": group.json()["revision"],
            "owner_id": None,
            "developer_ids": [people["ceshi002"], people["ceshi003"]],
            "designer_ids": [people["ceshi004"]],
        },
    )
    assert full.status_code == 200, full.text
    assert [v["completed_at"] is not None for v in full.json()["development_completions"]] == [
        True,
        False,
    ]
    assert (
        client.put(
            path + "/collaborators",
            headers=admin,
            json={
                "revision": full.json()["revision"],
                "owner_id": None,
                "developer_ids": [],
                "designer_ids": [],
            },
        ).status_code
        == 422
    )
    assert confirm_member(client, req["id"], tokens["ceshi004"]).status_code == 403
    with engine.connect() as db:
        with pytest.raises(DBAPIError):
            db.execute(
                text(
                    "UPDATE rd_requirement_participant SET completed_at=CURRENT_TIMESTAMP "
                    "WHERE requirement_id=:rid AND discipline='DESIGN'"
                ),
                {"rid": req["id"]},
            )
        db.rollback()
    for status in ["TESTING", "DONE"]:
        current = client.get(path, headers=admin).json()
        assert (
            client.patch(
                path + "/status",
                headers=admin,
                json={"revision": current["revision"], "status": status},
            ).status_code
            == 200
        )
    assert client.post(vpath + "/publish", headers=admin, json=body).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Release)) == 0
        assert db.get(Version, version["id"]).status == "READY"
    assert confirm_member(client, req["id"], tokens["ceshi003"]).status_code == 200
    published = client.post(vpath + "/publish", headers=admin, json=body)
    assert published.status_code == 200, published.text
    assert confirm_member(client, req["id"], tokens["ceshi002"]).status_code == 409
    assert client.post(vpath + "/publish", headers=admin, json=body).status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Release)) == 1
        assert db.get(Requirement, req["id"]).status == "ONLINE"
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(OperationLog.action == "CONFIRM_DEVELOPMENT_COMPLETION")
            )
            == 4
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(OperationLog.action == "RESET_DEVELOPMENT_COMPLETION")
            )
            == 1
        )
    # A legacy DONE record with no developers is never implicitly approved.
    from app.services.publish_check_service import PublishCheckService

    with Session(engine) as db:
        check = PublishCheckService(db).evaluate(db.get(Version, version["id"]))
        assert any(
            c["type"] == "DEVELOPMENT_COMPLETION_CHECK" and c["passed"] for c in check["checks"]
        )
    with engine.begin() as db:
        db.execute(
            text(
                "DELETE FROM rd_requirement_participant "
                "WHERE requirement_id=:rid AND discipline='DEVELOPMENT'"
            ),
            {"rid": req["id"]},
        )
    with Session(engine) as db:
        check = PublishCheckService(db).evaluate(db.get(Version, version["id"]))
        assert any(
            c["type"] == "DEVELOPMENT_COMPLETION_CHECK" and not c["passed"] for c in check["checks"]
        )


def exercise_completion_rollback_and_race(fixture, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    client, engine, _, admin = fixture
    people, tokens, req, _ = completion_team(fixture)
    path = f"/api/v1/requirements/{req['id']}"
    current = client.get(path, headers=admin).json()
    before = current["revision"]
    with Session(engine) as db:
        notifications_before = db.scalar(select(func.count()).select_from(Notification))
    original = RequirementCollaborationService.notify

    def fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("after confirmation, audit and notification writes")

    with monkeypatch.context() as patch:
        patch.setattr(RequirementCollaborationService, "notify", fail)
        with TestClient(app, raise_server_exceptions=False) as failing:
            assert (
                failing.post(
                    path + "/development-completion",
                    headers=tokens["ceshi002"],
                    json={"revision": before},
                ).status_code
                == 500
            )
    with Session(engine) as db:
        assert db.get(Requirement, req["id"]).revision == before
        assert db.scalar(select(func.count()).select_from(Notification)) == notifications_before
        assert all(at is None for at in db.scalars(select(RequirementParticipant.completed_at)))
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(OperationLog.action == "CONFIRM_DEVELOPMENT_COMPLETION")
            )
            == 0
        )
    barrier = Barrier(2)

    def confirm(name):
        barrier.wait(timeout=10)
        return client.post(
            path + "/development-completion", headers=tokens[name], json={"revision": before}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, ["ceshi002", "ceshi003"])) == [200, 409]
    roster = client.get(path + "/collaborators", headers=admin).json()
    assert sum(p["completed_at"] is not None for p in roster["development_completions"]) == 1
    pending = next(
        p["user_id"] for p in roster["development_completions"] if p["completed_at"] is None
    )
    name = next(n for n, uid in people.items() if uid == pending)
    assert confirm_member(client, req["id"], tokens[name]).status_code == 200


def exercise_publish_roster_serialization(fixture, monkeypatch):
    from concurrent.futures import TimeoutError
    from threading import Event

    from app.services.publish_check_service import PublishCheckService

    client, _engine, _, admin = fixture
    people, tokens, req, version = completion_team(fixture)
    for name in ["ceshi002", "ceshi003"]:
        assert confirm_member(client, req["id"], tokens[name]).status_code == 200
    path = f"/api/v1/requirements/{req['id']}"
    vpath = f"/api/v1/versions/{version['id']}"
    current = client.get(path, headers=admin).json()
    version = client.get(vpath, headers=admin).json()
    locked, proceed, attempting = Event(), Event(), Event()
    original = PublishCheckService.evaluate

    def pause(self, version, *, lock=False):
        result = original(self, version, lock=lock)
        if lock:
            locked.set()
            assert proceed.wait(10)
        return result

    def publish():
        return client.post(
            vpath + "/publish",
            headers=admin,
            json={
                "revision": version["revision"],
                "released_at": "2026-10-10T10:00:00Z",
                "release_notes": "并发分工不可绕过",
            },
        )

    def edit():
        attempting.set()
        return client.patch(
            path + "/collaborators",
            headers=admin,
            json={
                "revision": current["revision"],
                "kind": "DEVELOPMENT",
                "user_ids": [people["ceshi002"]],
            },
        )

    with monkeypatch.context() as patch:
        patch.setattr(PublishCheckService, "evaluate", pause)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pub = pool.submit(publish)
            assert locked.wait(10)
            writer = pool.submit(edit)
            assert attempting.wait(10)
            try:
                writer.result(timeout=0.2)
                raise AssertionError("assignment bypassed publish requirement locks")
            except TimeoutError:
                pass
            finally:
                proceed.set()
            assert pub.result(timeout=10).status_code == 200
            assert writer.result(timeout=10).status_code == 409
    roster = client.get(path + "/collaborators", headers=admin).json()
    assert len(roster["developers"]) == 2
    assert all(p["completed_at"] is not None for p in roster["development_completions"])

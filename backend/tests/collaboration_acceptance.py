"""Current workflow acceptance shared by PostgreSQL and MySQL 5.7."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from multiple_acceptance_migration import exercise_migration
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from app.models.entities import (
    CollaborationEvent,
    NotificationDelivery,
    Requirement,
    RequirementParticipant,
    RequirementStep,
    User,
)
from app.services.audit_service import AuditService
from app.services.delivery_service import DeliveryService


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


def setup_team(fixture, multiple_acceptance=False):
    client, engine, admin_id, admin = fixture
    system_id = create_test_system(engine)
    roles = {r["code"]: r["id"] for r in client.get("/api/v1/roles", headers=admin).json()}
    people, headers = {}, {}
    for name in ("dev1", "dev2", "accept", "other"):
        result = client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "username": "workflow-" + name,
                "display_name": name,
                "password": "Initial-workflow-123!",
                "role_ids": [roles["DEVELOPER"]],
            },
        )
        assert result.status_code == 200, result.text
        uid = result.json()["id"]
        with Session(engine) as db:
            db.get(User, uid).must_change_password = False
            db.commit()
        from app.core.security import create_access_token

        people[name] = uid
        headers[name] = RedactedHeaders(Authorization="Bearer " + create_access_token(uid))
    payload = [
        {"role": "CONFIRM", "user_id": admin_id},
        {"role": "DEVELOP", "user_id": people["dev1"]},
        {"role": "DEVELOP", "user_id": people["dev2"]},
        {"role": "ACCEPT", "user_id": people["accept"]},
        {"role": "DESIGN", "user_id": people["dev2"]},
    ]
    if multiple_acceptance:
        payload.append({"role": "ACCEPT", "user_id": people["other"]})
    result = client.post(
        "/api/v1/requirements",
        headers=admin,
        json={
            "title": "合并后跨数据库协作验收",
            "description": "验收范围",
            "requirement_type": "FEATURE",
            "system_id": system_id,
            "participants": payload,
        },
    )
    assert result.status_code == 200, result.text
    return people, headers, result.json(), payload


def exercise_workflow(fixture, scenario, monkeypatch):
    client, engine, _, admin = fixture
    multiple_acceptance = scenario in {"acceptance_multiple", "acceptance_race"}
    people, headers, req, payload = setup_team(fixture, multiple_acceptance)
    system_id = req["system_id"]
    if scenario == "acceptance_migration":
        exercise_migration(engine, req["id"], people["other"])
        return
    path = f"/api/v1/requirements/{req['id']}"

    def get():
        return client.get(path, headers=admin).json()

    def status(target, actor=admin, **extra):
        return client.patch(
            path + "/status",
            headers=actor,
            json={"status": target, "revision": get()["revision"], **extra},
        )

    def action(name, actor=admin, **extra):
        return client.post(
            path + "/workflow",
            headers=actor,
            json={"action": name, "revision": get()["revision"], **extra},
        )

    def ok(response):
        assert response.status_code == 200, response.text
        return response.json()

    if scenario == "scope":
        assert client.get(path, headers=headers["other"]).status_code == 404
        assert client.get(path, headers=headers["dev1"]).status_code == 200
        assert (
            client.put(
                path + "/participants",
                headers=headers["dev1"],
                json={"revision": req["revision"], "participants": payload},
            ).status_code
            == 403
        )
        assert action("CONFIRM", headers["dev1"]).status_code == 403
        return
    if scenario == "assignment_race":
        barrier = Barrier(2)

        def assign(_):
            barrier.wait(timeout=5)
            return client.put(
                path + "/participants",
                headers=admin,
                json={"revision": req["revision"], "participants": payload},
            ).status_code

        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(assign, range(2))) == [200, 409]
        return
    if scenario == "rollback":
        with Session(engine) as db:
            count = db.scalar(select(func.count(CollaborationEvent.id)))

        def fail(self, *args, **kwargs):
            raise RuntimeError("injected workflow audit failure")

        with monkeypatch.context() as patch:
            patch.setattr(AuditService, "log", fail)
            assert action("CONFIRM").status_code == 500
        assert get()["status"] == "DRAFT" and get()["revision"] == req["revision"]
        with Session(engine) as db:
            assert db.scalar(select(func.count(CollaborationEvent.id))) == count
        return
    if scenario == "bulk":
        second = ok(
            client.post(
                "/api/v1/requirements",
                headers=admin,
                json={
                    "title": "第二条批量需求",
                    "requirement_type": "FEATURE",
                    "system_id": system_id,
                    "description": "原子批量",
                },
            )
        )
        version = ok(
            client.post(
                "/api/v1/versions",
                headers=admin,
                json={
                    "system_id": system_id,
                    "version_no": "BULK-" + uuid4().hex[:8],
                    "name": "双数据库批量验证",
                },
            )
        )
        body = {
            "request_id": str(uuid4()),
            "version_revision": version["revision"],
            "items": [
                {"requirement_id": req["id"], "revision": req["revision"]},
                {"requirement_id": second["id"], "revision": second["revision"] + 1},
            ],
        }
        endpoint = f"/api/v1/versions/{version['id']}/requirements/batch"
        assert client.post(endpoint, headers=admin, json=body).status_code == 409
        assert get()["current_version_id"] is None
        body["items"][1]["revision"] = second["revision"]
        ok(client.post(endpoint, headers=admin, json=body))
        assert get()["current_version_id"] == version["id"]
        assert (
            client.get(f"/api/v1/requirements/{second['id']}", headers=admin).json()[
                "current_version_id"
            ]
            == version["id"]
        )
        assert client.post(endpoint, headers=admin, json=body).status_code == 409
        return
    if scenario == "notification":
        with Session(engine) as db:
            service = DeliveryService(db)
            assert service.expand() > 0
            db.commit()
            assert service.expand() == 0
            sent = 0
            while service.deliver_one():
                sent += 1
            assert sent > 0
            assert (
                db.scalar(
                    select(func.count(NotificationDelivery.id)).where(
                        NotificationDelivery.status == "SENT"
                    )
                )
                > 0
            )
        return
    if multiple_acceptance:
        assigned = ok(
            client.put(
                path + "/participants",
                headers=admin,
                json={"revision": get()["revision"], "participants": payload},
            )
        )
        assert {p["user_id"] for p in assigned["participants"] if p["role"] == "ACCEPT"} == {
            people["accept"],
            people["other"],
        }
    ok(action("CONFIRM"))
    if scenario == "design":
        ok(action("DESIGN_PENDING", headers["dev2"]))
        ok(action("DESIGN_START", headers["dev2"]))
    ok(status("DEVELOPING", headers["dev1"]))
    if scenario == "reconfirmation":
        ok(
            client.patch(
                path,
                headers=admin,
                json={"revision": get()["revision"], "description": "范围已修改"},
            )
        )
        assert status("TESTING", headers["dev1"]).status_code == 409
        ok(action("CONFIRM"))
    if scenario == "design":
        assert status("TESTING", headers["dev1"]).status_code == 409
        ok(action("DESIGN_DONE", headers["dev2"]))
    if scenario == "revocation":
        with Session(engine) as db:
            db.get(User, people["dev1"]).status = "DISABLED"
            db.commit()
        assert status("TESTING", headers["dev1"]).status_code in {401, 403}
        ok(status("TESTING", headers["dev2"]))
    else:
        ok(status("TESTING", headers["dev1"]))
    assert status("DONE", headers["dev2"]).status_code == 403
    assert (
        client.post(
            path + "/development-completion",
            headers=headers["dev2"],
            json={"revision": get()["revision"]},
        ).status_code
        == 404
    )
    if multiple_acceptance:
        before_revision = get()["revision"]
        with Session(engine) as db:
            event = db.scalar(
                select(CollaborationEvent).where(
                    CollaborationEvent.entity_id == req["id"],
                    CollaborationEvent.action == "STATUS_TESTING",
                )
            )
            assert {people["accept"], people["other"]} <= set(event.recipient_ids)
            assert all(
                DeliveryService(db).is_task(event, people[name]) for name in ("accept", "other")
            )
            DeliveryService(db).expand()
            assert set(
                db.scalars(
                    select(NotificationDelivery.user_id).where(
                        NotificationDelivery.event_id == event.id,
                        NotificationDelivery.channel == "SITE",
                    )
                )
            ) >= {people["accept"], people["other"]}
        if scenario == "acceptance_race":
            barrier = Barrier(2)

            def accept(name):
                barrier.wait()
                result = client.patch(
                    path + "/status",
                    headers=headers[name],
                    json={"status": "DONE", "revision": before_revision},
                )
                return name, result.status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(accept, ["accept", "other"]))
            assert sorted(code for _, code in results) == [200, 409]
            winner = people[next(name for name, code in results if code == 200)]
        else:
            ok(status("DONE", headers["other"]))
            winner = people["other"]
        assert get()["status"] == "DONE" and get()["revision"] == before_revision + 1
        assert status("DONE", headers["accept"]).status_code == 409
        with Session(engine) as db:
            records = list(
                db.scalars(
                    select(RequirementStep).where(
                        RequirementStep.requirement_id == req["id"],
                        RequirementStep.action == "STATUS_DONE",
                    )
                )
            )
            assert len(records) == 1 and records[0].actor_id == winner
            assert len([p for p in records[0].detail["participants"] if p["role"] == "ACCEPT"]) == 2
            assert (
                db.scalar(
                    select(func.count(CollaborationEvent.id)).where(
                        CollaborationEvent.entity_id == req["id"],
                        CollaborationEvent.action == "STATUS_DONE",
                    )
                )
                == 1
            )
        return
    ok(status("DONE", headers["accept"]))
    if scenario == "return":
        assert status("DEVELOPING", headers["dev1"]).status_code == 422
        ok(status("DEVELOPING", headers["dev1"], reason="重新开发验证"))
        ok(status("TESTING", headers["dev1"]))
        ok(status("DONE", headers["accept"]))
    with Session(engine) as db:
        assert db.get(Requirement, req["id"]).status == "DONE"
        assert (
            len(
                list(
                    db.scalars(
                        select(RequirementParticipant).where(
                            RequirementParticipant.requirement_id == req["id"],
                            RequirementParticipant.role == "DEVELOP",
                        )
                    )
                )
            )
            == 2
        )

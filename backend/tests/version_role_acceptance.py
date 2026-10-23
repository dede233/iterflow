"""Real-database permission and publication gates shared by both database paths."""

from datetime import UTC, datetime
from uuid import uuid4

from collaboration_acceptance import RedactedHeaders
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Notification, OperationLog, Release, Requirement, Version
from app.services.audit_service import AuditService

VERSION_PERMISSIONS = {
    "rd.version.view",
    "rd.version.create",
    "rd.version.edit",
    "rd.version.status",
    "rd.version.publish",
    "rd.requirement.view",
    "rd.release.view",
}


def exercise_version_role(fixture, role_code, monkeypatch):
    client, engine, _, admin = fixture
    role_ids = {r["code"]: r["id"] for r in client.get("/api/v1/roles", headers=admin).json()}
    suffix = uuid4().hex[:8]

    def account(code, number):
        username = f"ceshi{number:03}-{suffix}"
        created = client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "username": username,
                "display_name": username,
                "password": "ceshi-init-123",
                "role_ids": [role_ids[code]],
            },
        )
        assert created.status_code == 200, created.text
        login = client.post(
            "/api/v1/auth/login", json={"username": username, "password": "ceshi-init-123"}
        )
        assert login.status_code == 200
        changed = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": "Bearer " + login.json()["access_token"]},
            json={"current_password": "ceshi-init-123", "new_password": "ceshi123"},
        )
        assert changed.status_code == 200, changed.text
        return created.json()["id"], RedactedHeaders(
            Authorization="Bearer " + changed.json()["access_token"]
        )

    actor_id, actor = account(role_code, 1)
    dev1_id, dev1 = account("DEVELOPER", 2)
    dev2_id, dev2 = account("DEVELOPER", 3)
    me = client.get("/api/v1/auth/me", headers=actor).json()
    assert VERSION_PERMISSIONS <= set(me["permission_codes"])
    assert me["data_scope"] == ("ALL" if role_code == "PRODUCT_MANAGER" else "SELF")

    def ok(response):
        assert response.status_code == 200, response.text
        return response.json()

    def version(header, name):
        return ok(
            client.post(
                "/api/v1/versions",
                headers=header,
                json={
                    "version_no": f"VR-{name}-{suffix}",
                    "name": "权限实机版本",
                },
            )
        )

    first = version(actor, "first")
    second = version(actor, "second")
    path = f"/api/v1/versions/{second['id']}"
    foreign = version(admin, "foreign")
    foreign_path = f"/api/v1/versions/{foreign['id']}"
    body = {
        "released_at": datetime.now(UTC).isoformat(),
        "release_notes": "角色发布验收",
        "revision": 1,
    }
    expected = 200 if role_code == "PRODUCT_MANAGER" else 404
    assert client.get(foreign_path, headers=actor).status_code == expected
    if expected == 404:
        assert client.post(foreign_path + "/publish/check", headers=actor).status_code == 404
        assert client.post(foreign_path + "/publish", headers=actor, json=body).status_code == 404
        assert (
            client.patch(
                foreign_path, headers=actor, json={"name": "越界", "revision": 1}
            ).status_code
            == 404
        )
    for number, code in enumerate(("MEMBER", "DESIGNER", "TESTER"), 4):
        _, denied = account(code, number)
        assert (
            client.post(
                "/api/v1/versions", headers=denied, json={"version_no": "DENIED", "name": "拒绝"}
            ).status_code
            == 403
        )
        assert client.post(path + "/publish/check", headers=denied).status_code == 403
        assert client.post(path + "/publish", headers=denied, json=body).status_code == 403

    second = ok(
        client.patch(path, headers=actor, json={"name": "更新版本", "revision": second["revision"]})
    )
    stale = client.patch(path, headers=actor, json={"name": "旧修订", "revision": 1})
    assert stale.status_code == 409 and stale.json()["code"] == 40910
    req = ok(
        client.post(
            "/api/v1/requirements",
            headers=admin,
            json={
                "title": "全员开发确认门禁",
                "requirement_type": "FEATURE",
                "description": "角色回归",
                "owner_id": actor_id,
            },
        )
    )
    req_path = f"/api/v1/requirements/{req['id']}"
    ok(
        client.put(
            req_path + "/collaborators",
            headers=admin,
            json={
                "revision": req["revision"],
                "owner_id": actor_id,
                "developer_ids": [dev1_id, dev2_id],
                "designer_ids": [],
            },
        )
    )
    req = ok(client.get(req_path, headers=admin))
    ok(
        client.post(
            f"/api/v1/versions/{first['id']}/requirements",
            headers=actor,
            json={
                "requirement_id": req["id"],
                "revision": req["revision"],
                "version_revision": first["revision"],
            },
        )
    )
    req = ok(client.get(req_path, headers=admin))
    ok(
        client.post(
            path + "/requirements/move",
            headers=actor,
            json={
                "requirement_id": req["id"],
                "revision": req["revision"],
                "version_revision": second["revision"],
                "reason": "调整发布版本",
            },
        )
    )
    req = ok(client.get(req_path, headers=admin))
    second = ok(client.get(path, headers=actor))
    ok(
        client.request(
            "DELETE",
            path + f"/requirements/{req['id']}",
            headers=actor,
            json={
                "revision": req["revision"],
                "version_revision": second["revision"],
                "reason": "验证移出",
            },
        )
    )
    req = ok(client.get(req_path, headers=admin))
    second = ok(client.get(path, headers=actor))
    ok(
        client.post(
            path + "/requirements",
            headers=actor,
            json={
                "requirement_id": req["id"],
                "revision": req["revision"],
                "version_revision": second["revision"],
            },
        )
    )
    second = ok(client.get(path, headers=actor))
    for status in ("DEVELOPING", "TESTING", "READY"):
        second = ok(
            client.patch(
                path + "/status",
                headers=actor,
                json={"status": status, "revision": second["revision"]},
            )
        )
    body["revision"] = second["revision"]
    assert client.post(path + "/publish/check", headers=actor).status_code == 409
    assert client.post(path + "/publish", headers=actor, json=body).status_code == 409
    req = ok(client.get(req_path, headers=admin))
    for status in ("DEVELOPING", "TESTING"):
        req = ok(
            client.patch(
                req_path + "/status",
                headers=admin,
                json={"status": status, "revision": req["revision"]},
            )
        )
    assert (
        client.patch(
            req_path + "/status",
            headers=admin,
            json={"status": "DONE", "revision": req["revision"]},
        ).status_code
        == 409
    )
    for i, developer in enumerate((dev1, dev2)):
        ok(
            client.post(
                req_path + "/development-completion",
                headers=developer,
                json={"revision": req["revision"]},
            )
        )
        req = ok(client.get(req_path, headers=admin))
        if i == 0:
            assert (
                client.patch(
                    req_path + "/status",
                    headers=admin,
                    json={"status": "DONE", "revision": req["revision"]},
                ).status_code
                == 409
            )
            assert client.post(path + "/publish", headers=actor, json=body).status_code == 409
    ok(
        client.patch(
            req_path + "/status",
            headers=admin,
            json={"status": "DONE", "revision": req["revision"]},
        )
    )
    assert client.post(path + "/publish/check", headers=actor).status_code == 200
    assert (
        client.post(path + "/publish", headers=actor, json={**body, "revision": 1}).status_code
        == 409
    )

    with Session(engine) as db:
        before_notifications = db.scalar(select(func.count(Notification.id)))
    original = AuditService.log

    def fail_publish_audit(self, entity_type, entity_id, action, **kwargs):
        if action == "VERSION_PUBLISH":
            raise RuntimeError("injected publication failure")
        return original(self, entity_type, entity_id, action, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(AuditService, "log", fail_publish_audit)
        response = client.post(path + "/publish", headers=actor, json=body)
        assert response.status_code == 500, response.text
    with Session(engine) as db:
        assert db.get(Version, second["id"]).status == "READY"
        assert db.get(Requirement, req["id"]).status == "DONE"
        assert (
            db.scalar(select(func.count(Release.id)).where(Release.version_id == second["id"])) == 0
        )
        assert db.scalar(select(func.count(Notification.id))) == before_notifications
    result = ok(client.post(path + "/publish", headers=actor, json=body))
    assert result
    assert client.post(path + "/publish", headers=actor, json=body).status_code == 409
    with Session(engine) as db:
        assert db.get(Version, second["id"]).status == "RELEASED"
        assert db.get(Requirement, req["id"]).status == "ONLINE"
        assert (
            db.scalar(select(func.count(Release.id)).where(Release.version_id == second["id"])) == 1
        )
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "VERSION_PUBLISH",
                    OperationLog.entity_id == second["id"],
                    OperationLog.operator_id == actor_id,
                )
            )
            == 1
        )

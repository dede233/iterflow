"""The same restricted-account label checks run on both real database engines."""

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import BusinessModule, BusinessSystem, User
from app.models.enums import UserStatus
from app.repositories.feedback_repository import FeedbackRepository


class RedactedHeaders(dict):
    def __repr__(self):
        return "<authorization redacted>"


def exercise_feedback_reference_names(fixture):
    client, engine, _, admin = fixture
    permissions = {
        p["code"]: p["id"] for p in client.get("/api/v1/roles/permissions", headers=admin).json()
    }
    roles = {}
    for scope in ("SELF", "ALL"):
        response = client.post(
            "/api/v1/roles",
            headers=admin,
            json={
                "code": f"LABELS_{scope}",
                "name": f"名称验收 {scope}",
                "data_scope": scope,
                "permission_ids": [
                    permissions[code]
                    for code in ("rd.feedback.view", "rd.feedback.create", "rd.feedback.edit")
                ],
            },
        )
        assert response.status_code == 200, response.text
        roles[scope] = response.json()["id"]
    actors = {}
    for name, scope, label in (
        ("owner", "SELF", "提交人张三"),
        ("viewer", "ALL", "反馈查看人"),
        ("outsider", "SELF", "无关联成员"),
    ):
        response = client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "username": f"labels-{name}",
                "display_name": label,
                "password": "Labels-test-password!",
                "role_ids": [roles[scope]],
            },
        )
        assert response.status_code == 200, response.text
        uid = response.json()["id"]
        with Session(engine) as db:
            db.get(User, uid).must_change_password = False
            db.commit()
        actors[name] = RedactedHeaders(Authorization=f"Bearer {create_access_token(uid)}")

    with Session(engine) as db:
        system = BusinessSystem(code="LABEL_SYSTEM", name="中文历史系统")
        db.add(system)
        db.flush()
        module = BusinessModule(system_id=system.id, code="LABEL_MODULE", name="中文历史模块")
        db.add(module)
        db.commit()
        system_id, module_id = system.id, module.id

    expected = {
        "submitter_display_name": "提交人张三",
        "system_name": "中文历史系统",
        "module_name": "中文历史模块",
    }

    def assert_names(response):
        assert response.status_code == 200, response.text
        body = response.json()
        assert {key: body[key] for key in expected} == expected
        assert not {"password_hash", "username", "email", "role_ids"} & body.keys()
        return body

    created = assert_names(
        client.post(
            "/api/v1/feedbacks",
            headers=actors["owner"],
            json={
                "title": "名称展示真实验收",
                "feedback_type": "OTHER",
                "description": "仅关联名称且无目录管理权限",
                "system_id": system_id,
                "module_id": module_id,
            },
        )
    )
    path = f"/api/v1/feedbacks/{created['id']}"
    for name in ("owner", "viewer"):
        assert client.get("/api/v1/users", headers=actors[name]).status_code == 403
        assert client.get("/api/v1/systems", headers=actors[name]).status_code == 403
        assert_names(client.get(path, headers=actors[name]))
        listed = client.get("/api/v1/feedbacks", headers=actors[name]).json()["items"]
        assert len(listed) == 1
        assert {key: listed[0][key] for key in expected} == expected
    assert client.get(path, headers=actors["outsider"]).status_code == 404
    assert client.get("/api/v1/feedbacks", headers=actors["outsider"]).json()["items"] == []
    updated = assert_names(
        client.patch(path, headers=actors["owner"], json={"title": "更新后名称", "revision": 1})
    )
    assert_names(
        client.patch(
            path + "/status",
            headers=actors["viewer"],
            json={"status": "ACCEPTED", "revision": updated["revision"]},
        )
    )
    with Session(engine) as db:
        db.get(BusinessSystem, system_id).enabled = False
        db.get(BusinessModule, module_id).enabled = False
        db.get(User, created["submitter_id"]).status = UserStatus.DISABLED
        db.commit()
    assert_names(client.get(path, headers=actors["viewer"]))

    queries = []

    def count_query(_conn, _cursor, statement, _parameters, _context, _many):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", count_query)
    try:
        with Session(engine) as db:
            labels = FeedbackRepository(db).display_names([created["id"]] * 100)
            assert len(labels) == 1
            assert labels[created["id"]] == tuple(expected.values())
            assert FeedbackRepository(db).display_names([]) == {}
        assert len(queries) == 1
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

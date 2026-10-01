"""Phase 7 acceptance: real PostgreSQL rollback and restricted-role HTTP matrix."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_v1_e2e_postgres import postgres_e2e_engine as postgres_e2e_engine
from test_v1_e2e_postgres import postgres_http_client as postgres_http_client

from app.core.security import create_access_token
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
    RequirementStatus,
    VersionStatus,
)


def ready_chain(engine, user_id):
    with Session(engine) as db:
        version = Version(
            version_no=f"P7-{uuid4().hex[:24]}",
            name="Atomic acceptance",
            status=VersionStatus.READY,
            created_by=user_id,
        )
        db.add(version)
        db.flush()
        requirement = Requirement(
            requirement_no=f"P7-{uuid4().hex[:24]}",
            title="Atomic requirement",
            requirement_type="FEATURE",
            description="acceptance",
            status=RequirementStatus.DONE,
            current_version_id=version.id,
            created_by=user_id,
        )
        db.add(requirement)
        db.flush()
        feedback = Feedback(
            feedback_no=f"P7-{uuid4().hex[:24]}",
            title="Atomic feedback",
            feedback_type=FeedbackType.OTHER,
            description="acceptance",
            status=FeedbackStatus.REQUIREMENT_LINKED,
            submitter_id=user_id,
            main_requirement_id=requirement.id,
            created_by=user_id,
        )
        db.add(feedback)
        db.flush()
        db.add_all(
            [
                RequirementFeedback(requirement_id=requirement.id, feedback_id=feedback.id),
                VersionRequirement(version_id=version.id, requirement_id=requirement.id),
            ]
        )
        db.commit()
        return version.id, requirement.id, feedback.id


def snapshot(engine, ids):
    with Session(engine) as db:
        v, r, f = (
            db.get(model, key)
            for model, key in zip((Version, Requirement, Feedback), ids, strict=True)
        )
        return (
            (v.status, v.revision, v.released_at),
            (r.status, r.revision),
            (f.status, f.revision),
            db.scalar(select(func.count(Release.id))),
            db.scalar(select(func.count(OperationLog.id))),
            db.scalar(select(func.count(Notification.id))),
        )


@pytest.mark.parametrize(
    "statement_prefix",
    [
        "update rd_version ",
        "update rd_requirement ",
        "update rd_feedback ",
        "insert into rd_release ",
        "insert into sys_operation_log ",
        "insert into sys_notification ",
    ],
    ids=["Version", "Requirement", "Feedback", "Release", "Audit", "Notification"],
)
def test_publish_http_rolls_back_after_each_real_database_write(
    postgres_e2e_engine,
    postgres_http_client,
    statement_prefix,
):
    engine, user_id, headers = postgres_e2e_engine
    ids = ready_chain(engine, user_id)
    before = snapshot(engine, ids)
    injected = []

    def fail_after_write(_conn, _cursor, statement, _params, _context, _many):
        if statement.lower().startswith(statement_prefix):
            injected.append(statement_prefix)
            raise RuntimeError("Phase 7 injected database-write failure")

    event.listen(engine, "after_cursor_execute", fail_after_write)
    try:
        response = postgres_http_client.post(
            f"/api/v1/versions/{ids[0]}/publish",
            headers=headers,
            json={
                "revision": 1,
                "released_at": datetime.now(UTC).isoformat(),
                "release_notes": "Atomic failure acceptance",
            },
        )
    finally:
        event.remove(engine, "after_cursor_execute", fail_after_write)
    assert injected == [statement_prefix], "Fault must occur after the intended SQL write"
    assert response.status_code == 500
    assert snapshot(engine, ids) == before, "All six stores and revisions must roll back"
    # Retry the same revision after removing the fault: the transaction can still succeed.
    retry = postgres_http_client.post(
        f"/api/v1/versions/{ids[0]}/publish",
        headers=headers,
        json={
            "revision": 1,
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": "retry",
        },
    )
    assert retry.status_code == 200, retry.text
    after = snapshot(engine, ids)
    assert [row[0] for row in after[:3]] == [
        VersionStatus.RELEASED,
        RequirementStatus.ONLINE,
        FeedbackStatus.ONLINE,
    ]
    assert after[3] == before[3] + 1
    assert after[4] == before[4] + 4
    assert after[5] == before[5] + 1


READ_CODES = {
    "rd.feedback.view",
    "rd.feedback.create",
    "rd.requirement.view",
    "rd.version.view",
    "rd.release.view",
    "dashboard.view",
    "sys.audit.view",
    "sys.user.view",
    "sys.role.view",
    "sys.system.view",
    "sys.system.manage",
    "sys.file.upload",
    "sys.file.download",
    "sys.file.delete",
}


def actor(db, codes, scope):
    suffix = uuid4().hex
    user = User(
        username=suffix, display_name=suffix, password_hash="test-only", must_change_password=False
    )
    role = Role(code=suffix, name=suffix, data_scope=scope, enabled=True, is_system=False)
    db.add_all([user, role])
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    for code in codes:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, name=code)
            db.add(permission)
            db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    return user.id, {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def matrix(postgres_e2e_engine, postgres_http_client):
    engine, _, _ = postgres_e2e_engine
    with Session(engine) as db:
        actors = {
            "none": actor(db, set(), DataScope.ALL),
            "self": actor(db, READ_CODES, DataScope.SELF),
            "all": actor(db, READ_CODES, DataScope.ALL),
            "other": actor(db, READ_CODES, DataScope.SELF),
            "dashboard_only": actor(db, {"dashboard.view"}, DataScope.ALL),
            "audit_only": actor(db, {"sys.audit.view"}, DataScope.ALL),
            "version_only": actor(db, {"rd.version.view"}, DataScope.ALL),
            "requirement_only": actor(db, {"rd.requirement.view"}, DataScope.ALL),
        }
        objects = {}
        for owner in ("self", "other"):
            user_id = actors[owner][0]
            suffix = uuid4().hex
            f = Feedback(
                feedback_no=suffix,
                title=suffix,
                feedback_type=FeedbackType.OTHER,
                description=suffix,
                submitter_id=user_id,
                created_by=user_id,
            )
            r = Requirement(
                requirement_no=suffix,
                title=suffix,
                requirement_type="FEATURE",
                description=suffix,
                created_by=user_id,
                owner_id=user_id,
            )
            v = Version(version_no=suffix, name=suffix, created_by=user_id, owner_id=user_id)
            db.add_all([f, r, v])
            db.flush()
            release = Release(version_id=v.id, released_at=datetime.now(UTC), release_notes=suffix)
            db.add(release)
            db.flush()
            log = OperationLog(
                entity_type="FEEDBACK", entity_id=f.id, action="CREATE", operator_id=user_id
            )
            notification = Notification(user_id=user_id, title=suffix, content=suffix)
            db.add_all([log, notification])
            db.flush()
            objects[owner] = {
                "feedback": f.id,
                "requirement": r.id,
                "version": v.id,
                "release": release.id,
                "audit": log.id,
                "notification": notification.id,
            }
        db.commit()
    return postgres_http_client, actors, objects


@pytest.mark.parametrize("domain", ["feedback", "requirement", "version", "release", "audit"])
def test_restricted_role_detail_matrix(matrix, domain):
    client, actors, objects = matrix
    route = {
        "feedback": "feedbacks",
        "requirement": "requirements",
        "version": "versions",
        "release": "releases",
        "audit": "audits",
    }[domain]
    own = f"/api/v1/{route}/{objects['self'][domain]}"
    foreign = f"/api/v1/{route}/{objects['other'][domain]}"
    for name, path, expected in [
        ("none", own, 403),
        ("self", own, 200),
        ("self", foreign, 404),
        ("all", foreign, 200),
    ]:
        response = client.get(path, headers=actors[name][1])
        assert response.status_code == expected, (domain, name, response.text)


def test_dashboard_and_audit_cannot_replace_domain_permissions(matrix):
    client, actors, objects = matrix
    assert client.get("/api/v1/dashboard/overview", headers=actors["none"][1]).status_code == 403
    for name in ("self", "all", "dashboard_only"):
        response = client.get("/api/v1/dashboard/overview", headers=actors[name][1])
        assert response.status_code == 200
        data = response.json()
        if name == "self":
            assert data["feedback"]["total_count"] == 1
            assert all(
                a["entity_id"] != objects["other"]["feedback"]
                for a in data["activities"]
                if a["entity_type"] == "FEEDBACK"
            )
        elif name == "all":
            assert data["feedback"]["total_count"] >= 2
        else:
            assert all(
                data[k] is None for k in ("feedback", "requirements", "versions", "releases")
            )
            assert data["activities"] == []
    audits = client.get("/api/v1/audits", headers=actors["audit_only"][1])
    assert audits.status_code == 200 and audits.json()["items"] == []
    for name in ("dashboard_only", "audit_only"):
        for domain, route in [
            ("feedback", "feedbacks"),
            ("requirement", "requirements"),
            ("version", "versions"),
            ("release", "releases"),
        ]:
            assert (
                client.get(
                    f"/api/v1/{route}/{objects['self'][domain]}", headers=actors[name][1]
                ).status_code
                == 403
            )
    for name, path in [
        ("version_only", f"/api/v1/versions/{objects['self']['version']}/requirements"),
        ("requirement_only", f"/api/v1/requirements/{objects['self']['requirement']}/feedbacks"),
    ]:
        assert client.get(path, headers=actors[name][1]).status_code == 403


def test_global_management_user_and_notification_matrix(matrix, postgres_e2e_engine):
    client, actors, objects = matrix
    for route in ("users", "roles", "systems"):
        assert client.get(f"/api/v1/{route}", headers=actors["none"][1]).status_code == 403
        assert client.get(f"/api/v1/{route}", headers=actors["all"][1]).status_code == 200
    own_user = actors["self"][0]
    other_user = actors["other"][0]
    assert client.get(f"/api/v1/users/{own_user}", headers=actors["self"][1]).status_code == 200
    assert client.get(f"/api/v1/users/{other_user}", headers=actors["self"][1]).status_code == 403
    assert client.get("/api/v1/roles", headers=actors["self"][1]).status_code == 403
    assert client.get("/api/v1/systems", headers=actors["self"][1]).status_code == 200
    assert client.get("/api/v1/systems/manage", headers=actors["self"][1]).status_code == 403
    assert client.get("/api/v1/systems/manage", headers=actors["all"][1]).status_code == 200
    foreign = objects["other"]["notification"]
    for name in ("self", "all"):
        response = client.post(f"/api/v1/notifications/{foreign}/read", headers=actors[name][1])
        assert response.status_code == 200 and response.json() == {"ok": True}
        with Session(postgres_e2e_engine[0]) as db:
            assert db.get(Notification, foreign).read_at is None
        assert foreign not in {
            n["id"] for n in client.get("/api/v1/notifications", headers=actors[name][1]).json()
        }
    assert (
        client.post(f"/api/v1/notifications/{foreign}/read", headers=actors["other"][1]).status_code
        == 200
    )


def test_attachment_and_generic_delete_matrix(matrix):
    client, actors, objects = matrix
    own = f"/api/v1/feedbacks/{objects['self']['feedback']}/attachments"
    foreign = f"/api/v1/feedbacks/{objects['other']['feedback']}/attachments"
    for name, path, expected in [
        ("none", own, 403),
        ("self", own, 200),
        ("self", foreign, 404),
        ("all", foreign, 200),
    ]:
        assert client.get(path, headers=actors[name][1]).status_code == expected
    uploaded = client.post(
        "/api/v1/files",
        headers=actors["other"][1],
        files={"file": ("matrix.txt", b"Phase 7 file security", "text/plain")},
    )
    assert uploaded.status_code in (200, 201), uploaded.text
    file_id = uploaded.json()["id"]
    for name, expected in [("none", 403), ("self", 404), ("other", 200), ("all", 200)]:
        assert (
            client.get(f"/api/v1/files/{file_id}/download", headers=actors[name][1]).status_code
            == expected
        )
    assert client.delete(f"/api/v1/files/{file_id}", headers=actors["none"][1]).status_code == 403
    assert client.delete(f"/api/v1/files/{file_id}", headers=actors["self"][1]).status_code == 404
    assert client.delete(f"/api/v1/files/{file_id}", headers=actors["all"][1]).status_code == 204
    own_upload = client.post(
        "/api/v1/files",
        headers=actors["self"][1],
        files={"file": ("self.txt", b"SELF delete acceptance", "text/plain")},
    )
    assert own_upload.status_code in (200, 201), own_upload.text
    assert (
        client.delete(
            f"/api/v1/files/{own_upload.json()['id']}", headers=actors["self"][1]
        ).status_code
        == 204
    )

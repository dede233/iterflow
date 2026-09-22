from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    Feedback,
    OperationLog,
    Permission,
    Release,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    FeedbackType,
    FeedbackUrgency,
    ReleaseResult,
    RequirementSource,
    RequirementStatus,
    UserStatus,
    VersionStatus,
)

AuditFixture = tuple[TestClient, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def audit_api(tmp_path: Path) -> Iterator[AuditFixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'audit-api.db'}", connect_args={"check_same_thread": False}
    )
    tables = (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        Feedback.__table__,
        Requirement.__table__,
        Version.__table__,
        Release.__table__,
        OperationLog.__table__,
    )
    for table in tables:
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission, Feedback, Requirement, Version, Release, OperationLog):
        counter = iter(range(1, 10_000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        permissions = {
            code: Permission(code=code, name=code)
            for code in ("*", "sys.audit.view", "rd.feedback.view")
        }
        self_auditor_role = Role(code="SELF_AUDITOR", name="个人审计", data_scope=DataScope.SELF)
        all_auditor_role = Role(code="ALL_AUDITOR", name="全量反馈审计", data_scope=DataScope.ALL)
        no_audit_role = Role(code="NO_AUDIT", name="无审计权限", data_scope=DataScope.SELF)
        admin_role = Role(code="ADMIN", name="管理员", data_scope=DataScope.ALL)
        session.add_all(
            [
                self_auditor_role,
                all_auditor_role,
                no_audit_role,
                admin_role,
                *permissions.values(),
            ]
        )
        session.flush()

        def grant(role: Role, *codes: str) -> None:
            session.add_all(
                [
                    RolePermission(role_id=role.id, permission_id=permissions[code].id)
                    for code in codes
                ]
            )

        grant(self_auditor_role, "sys.audit.view", "rd.feedback.view")
        grant(all_auditor_role, "sys.audit.view", "rd.feedback.view")
        grant(no_audit_role, "rd.feedback.view")
        grant(admin_role, "*")

        def user(username: str) -> User:
            return User(
                username=username,
                display_name=username.title(),
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )

        alice, bob, auditor, blocked, admin = (
            user("alice"),
            user("bob"),
            user("auditor"),
            user("blocked"),
            user("admin"),
        )
        session.add_all([alice, bob, auditor, blocked, admin])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=alice.id, role_id=self_auditor_role.id),
                UserRole(user_id=bob.id, role_id=self_auditor_role.id),
                UserRole(user_id=auditor.id, role_id=all_auditor_role.id),
                UserRole(user_id=blocked.id, role_id=no_audit_role.id),
                UserRole(user_id=admin.id, role_id=admin_role.id),
            ]
        )

        alice_feedback = Feedback(
            feedback_no="FB-AUDIT-001",
            title="Alice feedback",
            feedback_type=FeedbackType.SYSTEM_ISSUE,
            urgency=FeedbackUrgency.NORMAL,
            status=FeedbackStatus.NEW,
            submitter_id=alice.id,
            description="Alice detail",
            created_by=alice.id,
        )
        bob_feedback = Feedback(
            feedback_no="FB-AUDIT-002",
            title="Bob feedback",
            feedback_type=FeedbackType.SYSTEM_ISSUE,
            urgency=FeedbackUrgency.NORMAL,
            status=FeedbackStatus.NEW,
            submitter_id=bob.id,
            description="Bob detail",
            created_by=bob.id,
        )
        requirement = Requirement(
            requirement_no="REQ-AUDIT-001",
            title="Hidden requirement",
            requirement_type="FEATURE",
            source=RequirementSource.DIRECT,
            status=RequirementStatus.DRAFT,
            description="Requirement detail",
            owner_id=bob.id,
            created_by=bob.id,
        )
        version = Version(
            version_no="V-AUDIT-001",
            name="Audit version",
            status=VersionStatus.PLANNING,
            owner_id=alice.id,
            created_by=alice.id,
        )
        session.add_all([alice_feedback, bob_feedback, requirement, version])
        session.flush()
        release = Release(
            version_id=version.id,
            released_at=datetime.now(UTC),
            result=ReleaseResult.SUCCESS,
            release_notes="Audit release",
            created_by=alice.id,
        )
        session.add(release)
        session.flush()

        base = datetime.now(UTC) - timedelta(hours=1)
        logs = [
            OperationLog(
                entity_type="FEEDBACK",
                entity_id=alice_feedback.id,
                action="STATUS_CHANGE",
                operator_id=alice.id,
                before_data={"status": "NEW"},
                after_data={"status": "ACCEPTED"},
                created_at=base,
            ),
            OperationLog(
                entity_type="FEEDBACK",
                entity_id=bob_feedback.id,
                action="UPDATE",
                operator_id=bob.id,
                before_data={"title": "old"},
                after_data={"title": "new"},
                created_at=base + timedelta(minutes=1),
            ),
            OperationLog(
                entity_type="REQUIREMENT",
                entity_id=requirement.id,
                action="UPDATE",
                operator_id=bob.id,
                before_data={"priority": "P2"},
                after_data={"priority": "P1"},
                created_at=base + timedelta(minutes=2),
            ),
            OperationLog(
                entity_type="RELEASE",
                entity_id=release.id,
                action="RELEASE_CREATE",
                operator_id=alice.id,
                after_data={"version_id": version.id},
                created_at=base + timedelta(minutes=3),
            ),
        ]
        session.add_all(logs)
        session.commit()

        ids = {
            "alice": alice.id,
            "bob": bob.id,
            "auditor": auditor.id,
            "blocked": blocked.id,
            "admin": admin.id,
            "alice_log": logs[0].id,
            "bob_log": logs[1].id,
            "requirement_log": logs[2].id,
            "alice_feedback": alice_feedback.id,
        }
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(user_id)}"}
            for name, user_id in ids.items()
            if name in {"alice", "bob", "auditor", "blocked", "admin"}
        }
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, headers, ids
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def test_audit_list_paginates_and_applies_all_filters(audit_api: AuditFixture):
    client, headers, ids = audit_api

    page = client.get("/api/v1/audits", headers=headers["admin"], params={"page": 1, "size": 1})
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 4
    assert page.json()["size"] == 1
    assert len(page.json()["items"]) == 1

    filtered = client.get(
        "/api/v1/audits",
        headers=headers["admin"],
        params={
            "entity_type": "FEEDBACK",
            "entity_id": ids["alice_feedback"],
            "action": "STATUS_CHANGE",
            "operator_id": ids["alice"],
            "time_from": "2000-01-01T00:00:00Z",
            "time_to": "2100-01-01T00:00:00Z",
        },
    )
    assert filtered.status_code == 200, filtered.text
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == ids["alice_log"]


def test_audit_detail_exposes_operator_and_before_after(audit_api: AuditFixture):
    client, headers, ids = audit_api

    response = client.get(f"/api/v1/audits/{ids['alice_log']}", headers=headers["admin"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operator"] == {
        "id": ids["alice"],
        "username": "alice",
        "display_name": "Alice",
    }
    assert body["before"] == {"status": "NEW"}
    assert body["after"] == {"status": "ACCEPTED"}


def test_audit_requires_its_own_permission(audit_api: AuditFixture):
    client, headers, _ids = audit_api

    assert client.get("/api/v1/audits", headers=headers["blocked"]).status_code == 403


def test_audit_respects_entity_permission_and_self_all_scope(audit_api: AuditFixture):
    client, headers, ids = audit_api

    # SELF sees only audit records for Alice's own feedback.
    self_list = client.get("/api/v1/audits", headers=headers["alice"])
    assert self_list.status_code == 200
    assert [item["id"] for item in self_list.json()["items"]] == [ids["alice_log"]]
    assert (
        client.get(f"/api/v1/audits/{ids['bob_log']}", headers=headers["alice"]).status_code == 404
    )

    # ALL expands feedback scope, but not the entity permissions.  This auditor
    # cannot use the Audit Center to view Requirement logs.
    all_list = client.get("/api/v1/audits", headers=headers["auditor"])
    assert all_list.status_code == 200
    assert {item["id"] for item in all_list.json()["items"]} == {
        ids["alice_log"],
        ids["bob_log"],
    }
    requirement_filter = client.get(
        "/api/v1/audits",
        headers=headers["auditor"],
        params={"entity_type": "REQUIREMENT"},
    )
    assert requirement_filter.status_code == 403
    assert (
        client.get(
            f"/api/v1/audits/{ids['requirement_log']}", headers=headers["auditor"]
        ).status_code
        == 404
    )


def test_static_openapi_declares_audit_center_contract():
    spec_dir = Path(__file__).resolve().parents[2] / "spec"
    for filename in ("openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"):
        document = yaml.safe_load((spec_dir / filename).read_text(encoding="utf-8"))
        assert "/audits" in document["paths"]
        assert "/audits/{audit_id}" in document["paths"]
        assert document["paths"]["/audits"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"] == {"$ref": "#/components/schemas/AuditPage"}

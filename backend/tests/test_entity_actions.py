from collections import defaultdict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.database import Base, get_db
from app.core.exceptions import NotFoundError
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    AttachmentRelation,
    CollaborationEvent,
    Comment,
    Feedback,
    FeedbackRecipient,
    FileObject,
    Notification,
    OperationLog,
    Permission,
    Requirement,
    RequirementFeedback,
    RequirementParticipant,
    RequirementStep,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope, NotificationType, StorageDriver
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.entity_actions import EntityDelete
from app.schemas.version import AddRequirementRequest, BulkAddRequirements
from app.services.audit_service import AuditService
from app.services.delivery_service import DeliveryService
from app.services.entity_actions_service import EntityActionsService
from app.services.version_service import VersionService


@pytest.fixture
def actions_api(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'entity-actions.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    counters = defaultdict(lambda: iter(range(1, 100000)))

    def assign(mapper, _connection, item):
        pk = mapper.primary_key
        if len(pk) == 1 and isinstance(pk[0].type, BigInteger) and getattr(item, pk[0].key) is None:
            setattr(item, pk[0].key, next(counters[mapper.class_]))

    event.listen(Base, "before_insert", assign, propagate=True)
    with Session(engine, expire_on_commit=False) as db:
        roles = {
            name: Role(code=name, name=name, data_scope=scope)
            for name, scope in (
                ("ALLTEST", DataScope.ALL),
                ("SELFTEST", DataScope.SELF),
                ("READER", DataScope.ALL),
            )
        }
        codes = [
            "rd.requirement.view",
            "rd.requirement.edit",
            "rd.requirement.status",
            "rd.feedback.view",
            "rd.feedback.edit",
            "rd.feedback.convert",
            "rd.feedback.create",
        ]
        permissions = {code: Permission(code=code, name=code) for code in codes}
        db.add_all([*roles.values(), *permissions.values()])
        db.flush()
        for name, role in roles.items():
            for code, permission in permissions.items():
                if name != "READER" or code.endswith(".view"):
                    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        users = {
            name: User(
                username=name, display_name=name, password_hash="unused", must_change_password=False
            )
            for name in ("boss", "alice", "bob", "reader")
        }
        db.add_all(users.values())
        db.flush()
        for name, user in users.items():
            role_name = (
                "ALLTEST" if name == "boss" else "READER" if name == "reader" else "SELFTEST"
            )
            db.add(UserRole(user_id=user.id, role_id=roles[role_name].id))
        db.commit()
        headers = {
            name: {"Authorization": "Bearer " + create_access_token(user.id)}
            for name, user in users.items()
        }
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db, headers, users
        app.dependency_overrides.clear()
    event.remove(Base, "before_insert", assign)
    engine.dispose()


def req(db, owner, n, **kwargs):
    item = Requirement(
        requirement_no=f"REQ-{n}",
        title=f"需求{n}",
        requirement_type="FEATURE",
        description="需要处理的内容",
        created_by=owner.id,
        updated_by=owner.id,
        **kwargs,
    )
    db.add(item)
    db.flush()
    db.add(RequirementParticipant(requirement_id=item.id, user_id=owner.id, role="CONFIRM"))
    db.commit()
    return item


def feedback(db, owner, n, **kwargs):
    item = Feedback(
        feedback_no=f"FB-{n}",
        title=f"反馈{n}",
        feedback_type="SYSTEM_ISSUE",
        description="具体反馈",
        submitter_id=owner.id,
        created_by=owner.id,
        **kwargs,
    )
    db.add(item)
    db.flush()
    db.add(FeedbackRecipient(feedback_id=item.id, user_id=owner.id))
    db.commit()
    return item


def delete(client, headers, kind, item, **kwargs):
    return client.request(
        "DELETE",
        f"/api/v1/{kind}/{item.id}",
        headers=headers,
        json={"revision": item.revision, "reason": "误建记录", **kwargs},
    )


def test_delete_preserves_rows_history_and_hides_every_read(actions_api):
    client, db, headers, users = actions_api
    item = feedback(db, users["alice"], 1)
    file = FileObject(
        storage_key="test/file",
        original_name="old.txt",
        size=2,
        mime_type="text/plain",
        sha256="x" * 64,
        storage_driver=StorageDriver.LOCAL,
        created_by=users["alice"].id,
    )
    db.add(file)
    db.flush()
    db.add(AttachmentRelation(file_id=file.id, entity_type="FEEDBACK", entity_id=item.id))
    db.add(
        Comment(
            entity_type="FEEDBACK",
            entity_id=item.id,
            content="保留评论",
            created_by=users["alice"].id,
        )
    )
    db.add(
        Notification(
            user_id=users["alice"].id,
            title="保留历史通知",
            content="历史",
            type=NotificationType.SYSTEM,
        )
    )
    event_row = CollaborationEvent(
        entity_type="FEEDBACK",
        entity_id=item.id,
        action="RECIPIENT_ADDED",
        actor_id=users["alice"].id,
        recipient_ids=[users["alice"].id],
    )
    db.add(event_row)
    db.commit()
    response = delete(client, headers["alice"], "feedbacks", item)
    assert response.status_code == 200, response.text
    assert response.json() == {"id": item.id, "revision": 2, "deleted": True}
    db.refresh(item)
    assert item.deleted_at and item.deleted_by == users["alice"].id
    for suffix in (
        "",
        "/comments",
        "/attachments",
        f"/attachments/{file.id}/download",
        "/collaboration",
    ):
        assert (
            client.get(f"/api/v1/feedbacks/{item.id}{suffix}", headers=headers["boss"]).status_code
            == 404
        )
    assert client.get("/api/v1/feedbacks", headers=headers["boss"]).json()["total"] == 0
    assert not DashboardRepository(db).feedback_status_counts(users["boss"].id, DataScope.ALL)
    assert not DeliveryService(db).authorized(event_row, users["alice"])
    assert db.scalar(select(func.count()).select_from(Comment)) == 1
    assert db.scalar(select(func.count()).select_from(AttachmentRelation)) == 1
    assert db.scalar(select(func.count()).select_from(Notification)) == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(OperationLog)
            .where(OperationLog.action == "SOFT_DELETE")
        )
        == 1
    )
    assert delete(client, headers["boss"], "feedbacks", item).status_code == 404


def test_requirement_delete_scope_revision_state_and_audit(actions_api):
    client, db, headers, users = actions_api
    item = req(db, users["alice"], 1)
    assert delete(client, headers["bob"], "requirements", item).status_code == 404
    assert delete(client, headers["reader"], "requirements", item).status_code == 403
    assert delete(client, headers["alice"], "requirements", item, revision=99).status_code == 409
    assert delete(client, headers["alice"], "requirements", item, reason="  ").status_code == 422
    assert delete(client, headers["alice"], "requirements", item).status_code == 200
    assert (
        client.get(f"/api/v1/requirements/{item.id}/workflow", headers=headers["boss"]).status_code
        == 404
    )
    assert client.get("/api/v1/requirements", headers=headers["boss"]).json()["total"] == 0
    assert not DashboardRepository(db).requirement_status_counts(users["boss"].id, DataScope.ALL)
    other = req(db, users["alice"], 2, status="CONFIRMED")
    assert delete(client, headers["alice"], "requirements", other).status_code == 409


def test_delete_rejects_historical_and_duplicate_references(actions_api):
    client, db, headers, users = actions_api
    requirement = req(db, users["alice"], 1)
    version = Version(version_no="V-1", name="版本", owner_id=users["alice"].id)
    db.add(version)
    db.flush()
    db.add(
        VersionRequirement(
            version_id=version.id,
            requirement_id=requirement.id,
            active=False,
            added_by=users["alice"].id,
        )
    )
    target = feedback(db, users["alice"], 1)
    source = feedback(db, users["alice"], 2, status="DUPLICATE", duplicate_of_id=target.id)
    db.commit()
    assert delete(client, headers["boss"], "requirements", requirement).status_code == 409
    assert delete(client, headers["boss"], "feedbacks", target).status_code == 409
    assert source.duplicate_of_id == target.id
    unversioned = req(db, users["alice"], 2)
    db.add(
        RequirementFeedback(requirement_id=unversioned.id, feedback_id=target.id, is_primary=False)
    )
    db.commit()
    assert delete(client, headers["boss"], "requirements", unversioned).status_code == 409


def test_delete_rolls_back_when_audit_fails(actions_api, monkeypatch):
    _, db, _, users = actions_api
    item = req(db, users["alice"], 1)

    def fail(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "log", fail)
    with pytest.raises(RuntimeError):
        EntityActionsService(db).delete(
            "requirement", item.id, EntityDelete(revision=1, reason="误建需求"), users["alice"].id
        )
    db.rollback()
    db.refresh(item)
    assert item.deleted_at is None and item.revision == 1


def test_requirement_batch_keeps_success_and_reports_scope_and_revision(actions_api):
    client, db, headers, users = actions_api
    first = req(db, users["alice"], 1)
    stale = req(db, users["alice"], 2)
    hidden = req(db, users["bob"], 3)
    body = {
        "action": "CONFIRM",
        "items": [
            {"id": first.id, "revision": 1},
            {"id": stale.id, "revision": 90},
            {"id": hidden.id, "revision": 1},
        ],
    }
    response = client.post(
        "/api/v1/requirements/batch-actions", headers=headers["alice"], json=body
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [(r["success"], r["status_code"]) for r in results] == [
        (True, 200),
        (False, 409),
        (False, 404),
    ]
    assert results[0]["revision"] == 2 and results[2]["revision"] is None
    db.refresh(first)
    db.refresh(stale)
    db.refresh(hidden)
    assert [first.status, stale.status, hidden.status] == ["CONFIRMED", "DRAFT", "DRAFT"]
    assert db.scalar(select(func.count()).select_from(RequirementStep)) == 1
    second = client.post("/api/v1/requirements/batch-actions", headers=headers["alice"], json=body)
    assert second.json()["results"][0]["status_code"] == 409
    assert db.scalar(select(func.count()).select_from(RequirementStep)) == 1


def test_batch_feedback_recipient_permission_and_input_guards(actions_api):
    client, db, headers, users = actions_api
    first = feedback(db, users["boss"], 1)
    other = feedback(db, users["alice"], 2)
    body = {
        "action": "ACCEPTED",
        "items": [{"id": first.id, "revision": 1}, {"id": other.id, "revision": 1}],
    }
    assert (
        client.post(
            "/api/v1/feedbacks/batch-actions", headers=headers["reader"], json=body
        ).status_code
        == 403
    )
    response = client.post("/api/v1/feedbacks/batch-actions", headers=headers["boss"], json=body)
    assert [r["status_code"] for r in response.json()["results"]] == [200, 403]
    for invalid in (
        [],
        [{"id": first.id, "revision": 2}] * 2,
        [{"id": n, "revision": 1} for n in range(1, 52)],
    ):
        assert (
            client.post(
                "/api/v1/feedbacks/batch-actions",
                headers=headers["boss"],
                json={"action": "CLOSED", "items": invalid},
            ).status_code
            == 422
        )
    closed = client.post(
        "/api/v1/feedbacks/batch-actions",
        headers=headers["boss"],
        json={"action": "CLOSED", "items": [{"id": first.id, "revision": 2}]},
    )
    assert closed.json()["results"][0]["status_code"] == 422


def test_batch_unexpected_item_error_is_rolled_back_and_next_item_runs(actions_api, monkeypatch):
    client, db, headers, users = actions_api
    first = req(db, users["alice"], 1)
    second = req(db, users["alice"], 2)
    original = AuditService.log

    def fail_first(self, entity, entity_id, *args, **kwargs):
        if entity_id == first.id:
            raise RuntimeError("sensitive driver error")
        return original(self, entity, entity_id, *args, **kwargs)

    monkeypatch.setattr(AuditService, "log", fail_first)
    response = client.post(
        "/api/v1/requirements/batch-actions",
        headers=headers["alice"],
        json={
            "action": "CONFIRM",
            "items": [{"id": first.id, "revision": 1}, {"id": second.id, "revision": 1}],
        },
    )
    assert [r["status_code"] for r in response.json()["results"]] == [500, 200]
    assert "sensitive" not in response.text
    db.refresh(first)
    db.refresh(second)
    assert first.revision == 1 and first.status == "DRAFT" and second.status == "CONFIRMED"
    assert db.scalar(select(func.count()).select_from(RequirementStep)) == 1


def test_deleted_targets_cannot_be_linked_or_added_to_versions(actions_api):
    client, db, headers, users = actions_api
    requirement = req(db, users["alice"], 1)
    first = feedback(db, users["alice"], 1)
    removed = feedback(db, users["alice"], 2)
    assert delete(client, headers["alice"], "requirements", requirement).status_code == 200
    assert delete(client, headers["alice"], "feedbacks", removed).status_code == 200
    response = client.post(
        f"/api/v1/feedbacks/{first.id}/convert",
        headers=headers["alice"],
        json={"type": "LINK_EXISTING", "requirement_id": requirement.id, "revision": 1},
    )
    assert response.status_code == 404
    response = client.patch(
        f"/api/v1/feedbacks/{first.id}/status",
        headers=headers["alice"],
        json={"status": "DUPLICATE", "duplicate_of_id": removed.id, "revision": 1},
    )
    assert response.status_code == 422
    db.rollback()
    version = Version(version_no="V-1", name="版本", owner_id=users["alice"].id)
    db.add(version)
    db.commit()
    with pytest.raises(NotFoundError):
        VersionService(db).add_requirement(
            version.id,
            AddRequirementRequest(
                requirement_id=requirement.id,
                revision=2,
                version_revision=1,
            ),
            users["alice"].id,
            viewer_scope=DataScope.ALL,
            viewer_id=users["alice"].id,
        )
    db.rollback()
    with pytest.raises(NotFoundError):
        VersionService(db).bulk_add_requirements(
            version.id,
            BulkAddRequirements(
                version_revision=1,
                request_id=uuid4(),
                items=[{"requirement_id": requirement.id, "revision": 2}],
            ),
            users["alice"].id,
            viewer_scope=DataScope.ALL,
            viewer_id=users["alice"].id,
        )
    db.rollback()
    db.refresh(first)
    assert first.revision == 1 and first.main_requirement_id is None
    assert db.scalar(select(func.count()).select_from(RequirementFeedback)) == 0
    assert db.scalar(select(func.count()).select_from(VersionRequirement)) == 0

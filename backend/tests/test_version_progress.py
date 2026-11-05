"""Automatic version progress, using new temporary SQLite data only."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select
from test_entity_actions import actions_api as actions_api

from app.domain.version_progress import effective_version_status, loaded_version_status
from app.models.entities import (
    BusinessSystem,
    Feedback,
    OperationLog,
    Permission,
    Release,
    Requirement,
    RequirementFeedback,
    Role,
    RolePermission,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.version_repository import VersionRepository


@pytest.fixture
def progress_api(actions_api):
    client, db, headers, users = actions_api
    codes = {
        "rd.version.view",
        "rd.version.create",
        "rd.version.edit",
        "rd.version.status",
        "rd.version.publish",
        "rd.release.view",
        "rd.requirement.create",
    }
    db.add(BusinessSystem(id=1, code="PROGRESS", name="进度测试系统"))
    roles = list(db.scalars(select(Role).where(Role.code.in_(["ALLTEST", "SELFTEST"]))))
    for code in codes:
        permission = Permission(code=code, name=code)
        db.add(permission)
        db.flush()
        for role in roles:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
    return client, db, headers, users


def version(db, owner, number, states=(), *, stored="READY"):
    item = Version(
        system_id=1,
        version_no=f"VP-{number}",
        name=f"版本{number}",
        status=stored,
        created_by=owner.id,
        updated_by=owner.id,
    )
    db.add(item)
    db.flush()
    requirements = []
    for index, (status, confirmed, paused_from) in enumerate(states):
        req = Requirement(
            system_id=1,
            requirement_no=f"VP-REQ-{number}-{index}",
            title=f"需求{number}-{index}",
            requirement_type="FEATURE",
            description="完整需求内容",
            status=status,
            content_revision=2,
            confirmed_revision=2 if confirmed else None,
            created_by=owner.id,
            updated_by=owner.id,
            current_version_id=item.id,
            paused_from=paused_from,
        )
        db.add(req)
        db.flush()
        db.add(VersionRequirement(version_id=item.id, requirement_id=req.id, added_by=owner.id))
        requirements.append(req)
    db.commit()
    return item, requirements


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ([], "PLANNING"),
        ([("DRAFT", False, None)], "PLANNING"),
        ([("CONFIRMED", True, None)], "PLANNING"),
        ([("PLANNED", True, None)], "PLANNING"),
        ([("DESIGNING", True, None)], "DEVELOPING"),
        ([("DEVELOPING", True, None)], "DEVELOPING"),
        ([("TESTING", True, None)], "TESTING"),
        ([("DONE", True, None)], "READY"),
        ([("DONE", False, None)], "TESTING"),
        ([("TESTING", True, None), ("DONE", True, None)], "TESTING"),
        ([("DRAFT", False, None), ("DONE", True, None)], "DEVELOPING"),
        ([("CANCELED", True, None)], "PLANNING"),
        ([("CANCELED", True, None), ("DONE", True, None)], "DEVELOPING"),
        ([("PAUSED", True, "CONFIRMED")], "PLANNING"),
        ([("PAUSED", True, "TESTING")], "DEVELOPING"),
        ([("ONLINE", True, None)], "DEVELOPING"),
    ],
)
def test_policy_sql_api_filters_dashboard_agree_without_writes(progress_api, states, expected):
    client, db, headers, users = progress_api
    item, requirements = version(db, users["boss"], "MATRIX", states)
    db.refresh(item)  # Compare database-normalized timestamps (SQLite drops tzinfo).
    snapshot = (item.status, item.revision, item.updated_at)
    audits = db.scalar(select(func.count(OperationLog.id)))
    assert effective_version_status(item.status, requirements) == expected
    assert loaded_version_status(VersionRepository(db).get(item.id)) == expected
    response = client.get(f"/api/v1/versions/{item.id}", headers=headers["boss"])
    assert response.status_code == 200 and response.json()["status"] == expected
    listing = client.get("/api/v1/versions", headers=headers["boss"], params={"status": expected})
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["status"] == expected
    dashboard = DashboardRepository(db)
    assert dashboard.version_status_counts(users["boss"].id, DataScope.ALL) == {expected: 1}
    assert (
        loaded_version_status(dashboard.recent_active_versions(users["boss"].id, DataScope.ALL)[0])
        == expected
    )
    assert (item.status, item.revision, item.updated_at) == snapshot
    assert not db.dirty and not db.new
    assert db.scalar(select(func.count(OperationLog.id))) == audits


@pytest.mark.parametrize("terminal", ["RELEASED", "CANCELED"])
def test_real_terminals_override_projection(progress_api, terminal):
    client, db, headers, users = progress_api
    item, requirements = version(
        db, users["boss"], terminal, [("DONE", True, None)], stored=terminal
    )
    assert effective_version_status(item.status, requirements) == terminal
    assert (
        client.get(f"/api/v1/versions/{item.id}", headers=headers["boss"]).json()["status"]
        == terminal
    )
    assert DashboardRepository(db).recent_active_versions(users["boss"].id, DataScope.ALL) == []


def test_legacy_confirmation_and_inactive_or_deleted_rows(progress_api):
    client, db, headers, users = progress_api
    item, requirements = version(db, users["boss"], "LEGACY", [("DONE", False, None)])
    requirements[0].legacy_completed = True
    db.commit()
    assert (
        client.get(f"/api/v1/versions/{item.id}", headers=headers["boss"]).json()["status"]
        == "READY"
    )
    requirements[0].deleted_at = datetime.now(UTC)
    db.commit()
    assert (
        client.get(f"/api/v1/versions/{item.id}", headers=headers["boss"]).json()["status"]
        == "PLANNING"
    )
    requirements[0].deleted_at = None
    db.scalar(select(VersionRequirement)).active = False
    db.commit()
    assert (
        client.get(f"/api/v1/versions/{item.id}", headers=headers["boss"]).json()["status"]
        == "PLANNING"
    )


def test_create_with_completed_requirement_returns_ready_without_status_write(progress_api):
    client, db, headers, users = progress_api
    _, requirements = version(db, users["boss"], "SOURCE", [("DONE", True, None)])
    req = requirements[0]
    db.delete(db.scalar(select(VersionRequirement)))
    req.current_version_id = None
    db.commit()
    response = client.post(
        "/api/v1/versions",
        headers=headers["boss"],
        json={
            "version_no": "VP-NEW",
            "system_id": 1,
            "name": "直接关联完成需求",
            "requirement_id": req.id,
            "requirement_revision": req.revision,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "READY"
    assert db.get(Version, response.json()["id"]).status == "PLANNING"


def test_ready_roster_remains_editable_with_both_revisions(progress_api):
    client, db, headers, users = progress_api
    item, _ = version(db, users["boss"], "ROSTER", [("DONE", True, None)])
    req = Requirement(
        system_id=1,
        requirement_no="NEW-SCOPE",
        title="新需求",
        requirement_type="FEATURE",
        description="新增工作范围",
        created_by=users["boss"].id,
    )
    db.add(req)
    db.commit()
    payload = {
        "requirement_id": req.id,
        "revision": req.revision,
        "version_revision": item.revision,
    }
    added = client.post(
        f"/api/v1/versions/{item.id}/requirements", headers=headers["boss"], json=payload
    )
    assert added.status_code == 200, added.text
    assert added.json()["status"] == "DEVELOPING"
    removed = client.request(
        "DELETE",
        f"/api/v1/versions/{item.id}/requirements/{req.id}",
        headers=headers["boss"],
        json={
            "revision": req.revision,
            "version_revision": added.json()["revision"],
            "reason": "缩减范围",
        },
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "READY"
    stale = client.post(
        f"/api/v1/versions/{item.id}/requirements", headers=headers["boss"], json=payload
    )
    assert stale.status_code == 409


@pytest.mark.parametrize("target", ["PLANNING", "DEVELOPING", "TESTING", "READY"])
def test_old_manual_progress_requests_fail_without_writes(progress_api, target):
    client, db, headers, users = progress_api
    item, _ = version(db, users["boss"], target, stored="PLANNING")
    response = client.patch(
        f"/api/v1/versions/{item.id}/status",
        headers=headers["boss"],
        json={"status": target, "revision": item.revision},
    )
    assert response.status_code == 409 and "自动汇总" in response.json()["message"]
    assert item.revision == 1 and item.status == "PLANNING"
    assert db.scalar(select(func.count(OperationLog.id))) == 0


@pytest.mark.parametrize("stored", ["PLANNING", "DEVELOPING", "TESTING", "READY"])
def test_cancel_any_nonterminal_preserves_permissions_cas_audit(progress_api, stored):
    client, db, headers, users = progress_api
    item, _ = version(db, users["boss"], stored, [("DONE", True, None)], stored=stored)
    payload = {"status": "CANCELED", "revision": 1, "reason": "取消本次版本"}
    assert (
        client.patch(
            f"/api/v1/versions/{item.id}/status", headers=headers["reader"], json=payload
        ).status_code
        == 403
    )
    response = client.patch(
        f"/api/v1/versions/{item.id}/status", headers=headers["boss"], json=payload
    )
    assert response.status_code == 200 and response.json()["status"] == "CANCELED"
    assert (
        client.patch(
            f"/api/v1/versions/{item.id}/status", headers=headers["boss"], json=payload
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count(OperationLog.id))) == 1


def publish_payload(revision=1):
    return {
        "revision": revision,
        "released_at": datetime.now(UTC).isoformat(),
        "release_notes": "真实发布",
    }


def test_publish_derived_ready_is_atomic_and_does_not_fabricate_workflow(progress_api):
    client, db, headers, users = progress_api
    item, requirements = version(
        db, users["boss"], "PUBLISH", [("DONE", True, None)], stored="PLANNING"
    )
    req = requirements[0]
    feedback = Feedback(
        feedback_no="PROGRESS-FB",
        title="原始反馈",
        feedback_type="SYSTEM_ISSUE",
        description="完整反馈内容",
        status="REQUIREMENT_LINKED",
        submitter_id=users["boss"].id,
        main_requirement_id=req.id,
    )
    db.add(feedback)
    db.flush()
    db.add(RequirementFeedback(requirement_id=req.id, feedback_id=feedback.id, is_primary=True))
    db.commit()
    assert (
        client.post(
            f"/api/v1/versions/{item.id}/publish/check", headers=headers["boss"]
        ).status_code
        == 200
    )
    response = client.post(
        f"/api/v1/versions/{item.id}/publish", headers=headers["boss"], json=publish_payload()
    )
    assert response.status_code == 200, response.text
    assert item.status == "RELEASED" and req.status == "ONLINE" and feedback.status == "ONLINE"
    assert db.scalar(select(func.count(Release.id))) == 1
    actions = list(
        db.scalars(select(OperationLog.action).where(OperationLog.entity_type == "VERSION"))
    )
    assert actions == ["VERSION_PUBLISH"]
    assert (
        client.post(
            f"/api/v1/versions/{item.id}/publish", headers=headers["boss"], json=publish_payload()
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count(Release.id))) == 1


@pytest.mark.parametrize(
    "states",
    [
        [],
        [("DONE", False, None)],
        [("CANCELED", True, None)],
        [("PAUSED", True, "TESTING")],
        [("ONLINE", True, None)],
    ],
)
def test_nonpublishable_progress_blocks_even_legacy_ready(progress_api, states):
    client, db, headers, users = progress_api
    item, _ = version(db, users["boss"], "BLOCKED", states)
    assert (
        client.post(
            f"/api/v1/versions/{item.id}/publish/check", headers=headers["boss"]
        ).status_code
        == 409
    )
    response = client.post(
        f"/api/v1/versions/{item.id}/publish", headers=headers["boss"], json=publish_payload()
    )
    assert response.status_code == 409
    assert db.scalar(select(func.count(Release.id))) == 0
    assert item.status == "READY" and item.revision == 1


@pytest.mark.parametrize("viewer", ["alice", "reader"])
def test_hidden_requirements_block_without_ids_numbers_or_counts(progress_api, viewer):
    client, db, headers, users = progress_api
    item, requirements = version(db, users["alice"], "PRIVATE", [("DRAFT", False, None)] * 2)
    for req in requirements:
        req.created_by = users["bob"].id
    if viewer == "reader":
        role = db.scalar(select(Role).where(Role.code == "READER"))
        req_permission = db.scalar(
            select(Permission).where(Permission.code == "rd.requirement.view")
        )
        db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role.id, RolePermission.permission_id == req_permission.id
            )
        )
        for code in ["rd.version.view", "rd.version.publish"]:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
    for suffix in ["publish/check", "publish"]:
        response = client.post(
            f"/api/v1/versions/{item.id}/{suffix}",
            headers=headers[viewer],
            json=publish_payload() if suffix == "publish" else None,
        )
        assert response.status_code == 409, response.text
        data = response.json()["data"]
        assert data["blocking_requirements"] == []
        assert all(check["blocking_requirements"] == [] for check in data["checks"])
        assert "2 个" not in response.text
        assert all(req.requirement_no not in response.text for req in requirements)
    assert db.scalar(select(func.count(Release.id))) == 0

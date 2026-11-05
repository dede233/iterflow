from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_version_api import (
    _custom_creator_headers,
    _requirement,
    _version,
)
from test_version_api import (
    ver_api as _ver_api,
)

from app.models.entities import (
    CollaborationEvent,
    OperationLog,
    Requirement,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope, RequirementStatus
from app.services.audit_service import AuditService
from app.services.version_service import VersionService

ver_api = _ver_api


def snapshot(db):
    db.expire_all()
    return tuple(
        db.scalar(select(func.count()).select_from(model))
        for model in (Version, VersionRequirement, OperationLog, CollaborationEvent)
    )


def create_for(client, headers, requirement, **changes):
    body = {
        "system_id": 1,
        "version_no": "V-NEW",
        "name": "由需求创建版本",
        "requirement_id": requirement["id"],
        "requirement_revision": requirement["revision"],
    }
    body.update(changes)
    return client.post("/api/v1/versions", headers=headers, json=body)


def test_create_version_atomically_links_existing_requirement(ver_api):
    client, db, headers, ids = ver_api
    requirement = _requirement(client, headers["alice"])
    response = create_for(client, headers["alice"], requirement, owner_id=ids["bob"])
    assert response.status_code == 200, response.text
    version = response.json()
    assert version["revision"] == 2 and version["status"] == "PLANNING"
    latest = client.get(
        f"/api/v1/requirements/{requirement['id']}", headers=headers["alice"]
    ).json()
    assert latest["revision"] == requirement["revision"] + 1
    assert latest["status"] == requirement["status"]
    assert latest["current_version_id"] == version["id"]
    relation = db.scalar(select(VersionRequirement))
    assert relation.active and relation.requirement_id == requirement["id"]
    assert relation.added_by == ids["alice"]
    event = db.scalar(
        select(CollaborationEvent).where(CollaborationEvent.action == "RELATION_CHANGE")
    )
    assert ids["bob"] in event.recipient_ids
    actions = list(
        db.scalars(select(OperationLog.action).where(OperationLog.entity_type == "VERSION"))
    )
    assert actions == ["CREATE", "VERSION_REQUIREMENT_ADD"]


@pytest.mark.parametrize(
    "fields",
    [
        {"requirement_id": 1},
        {"requirement_revision": 1},
        {"requirement_id": 1, "requirement_revision": None},
        {"requirement_id": None, "requirement_revision": 1},
        {"requirement_id": 0, "requirement_revision": 1},
        {"requirement_id": 1, "requirement_revision": 0},
    ],
)
def test_create_requirement_fields_are_paired_and_positive(ver_api, fields):
    client, db, headers, _ids = ver_api
    before = snapshot(db)
    response = client.post(
        "/api/v1/versions",
        headers=headers["alice"],
        json={"system_id": 1, "version_no": "V-NEW", "name": "版本", **fields},
    )
    assert response.status_code == 422
    assert snapshot(db) == before


@pytest.mark.parametrize("missing", ["rd.version.edit", "rd.requirement.view"])
def test_link_requires_additional_permissions_without_restricting_plain_create(ver_api, missing):
    client, db, headers, _ids = ver_api
    requirement = _requirement(client, headers["alice"])
    actor = _custom_creator_headers(
        db,
        code="LIMITED",
        permissions={"rd.version.create", "rd.version.edit", "rd.requirement.view"} - {missing},
        scope=DataScope.ALL,
    )
    before = snapshot(db)
    assert create_for(client, actor, requirement).status_code == 403
    assert snapshot(db) == before
    plain = client.post(
        "/api/v1/versions",
        headers=actor,
        json={"system_id": 1, "version_no": "PLAIN", "name": "仅创建版本"},
    )
    assert plain.status_code == 200 and plain.json()["revision"] == 1
    before = snapshot(db)
    assert create_for(client, headers["version_editor"], requirement).status_code == 403
    assert snapshot(db) == before


def test_hidden_missing_and_soft_deleted_requirement_leave_no_empty_version(ver_api):
    client, db, headers, _ids = ver_api
    hidden = _requirement(client, headers["bob"])
    deleted = _requirement(client, headers["alice"])
    db.get(Requirement, deleted["id"]).deleted_at = datetime.now(UTC)
    db.commit()
    before = snapshot(db)
    for requirement in [hidden, deleted, {"id": 99999, "revision": 1}]:
        response = create_for(client, headers["alice"], requirement)
        assert response.status_code == 404
        assert snapshot(db) == before


def test_stale_revision_rolls_back_new_version_and_audits(ver_api):
    client, db, headers, _ids = ver_api
    requirement = _requirement(client, headers["alice"])
    db.get(Requirement, requirement["id"]).revision += 1
    db.commit()
    before = snapshot(db)
    response = create_for(client, headers["alice"], requirement)
    assert response.status_code == 409 and response.json()["code"] == 40910
    assert response.json()["data"]["current_revision"] == 2
    assert snapshot(db) == before
    assert db.get(Requirement, requirement["id"]).current_version_id is None


@pytest.mark.parametrize("status", [RequirementStatus.ONLINE, RequirementStatus.CANCELED])
def test_terminal_requirement_cannot_create_and_link_version(ver_api, status):
    client, db, headers, _ids = ver_api
    requirement = _requirement(client, headers["alice"])
    db.get(Requirement, requirement["id"]).status = status
    db.commit()
    before = snapshot(db)
    response = create_for(client, headers["alice"], requirement)
    assert response.status_code == 409 and response.json()["code"] == 40933
    assert snapshot(db) == before


@pytest.mark.parametrize("active_relation", [False, True])
def test_existing_version_pointer_or_relation_is_rejected_without_migration(
    ver_api, active_relation
):
    client, db, headers, _ids = ver_api
    requirement = _requirement(client, headers["alice"])
    version = _version(client, headers["alice"])
    if active_relation:
        db.add(
            VersionRequirement(
                version_id=version["id"], requirement_id=requirement["id"], active=True
            )
        )
    else:
        db.get(Requirement, requirement["id"]).current_version_id = version["id"]
    db.commit()
    before = snapshot(db)
    response = create_for(client, headers["alice"], requirement)
    assert response.status_code == 409 and response.json()["code"] == 40932
    assert response.json()["data"] is None
    assert snapshot(db) == before
    assert db.get(Requirement, requirement["id"]).revision == requirement["revision"]


@pytest.mark.parametrize("point", ["relation_audit", "after_relation"])
def test_create_relation_failures_roll_back_every_write(ver_api, point):
    client, db, headers, _ids = ver_api
    requirement = _requirement(client, headers["alice"])
    before = snapshot(db)
    original = AuditService.log

    def audit(self, *args, **kwargs):
        if args[2] == "VERSION_REQUIREMENT_ADD":
            raise RuntimeError("simulated audit failure")
        return original(self, *args, **kwargs)

    target = (
        patch.object(AuditService, "log", audit)
        if point == "relation_audit"
        else patch.object(
            VersionService,
            "_bump_version_revision",
            side_effect=RuntimeError("simulated post-relation failure"),
        )
    )
    with target:
        response = create_for(client, headers["alice"], requirement)
    assert response.status_code == 500
    assert snapshot(db) == before
    latest = db.get(Requirement, requirement["id"])
    assert latest.revision == requirement["revision"] and latest.current_version_id is None


@pytest.mark.parametrize("skip_precheck", [False, True])
def test_duplicate_version_number_is_precise_and_hides_existing_details(ver_api, skip_precheck):
    client, db, headers, _ids = ver_api
    _version(client, headers["bob"], version_no="秘密版本号", name="不可见版本名称")
    requirement = _requirement(client, headers["alice"])
    before = snapshot(db)
    original = VersionService._version_no_exists
    with (
        patch.object(VersionService, "_version_no_exists", return_value=False)
        if skip_precheck
        else patch.object(VersionService, "_version_no_exists", original)
    ):
        response = create_for(client, headers["alice"], requirement, version_no="秘密版本号")
    assert response.status_code == 409
    assert response.json()["code"] == 40934
    assert response.json()["data"] == {"field": "version_no", "reason": "duplicate"}
    assert response.json()["message"] == (
        "版本号「秘密版本号」已存在，请更换版本号；如需添加需求，请使用已有版本。"  # noqa: RUF001
    )
    assert "不可见版本名称" not in response.text
    assert snapshot(db) == before


def test_unrelated_integrity_failure_is_not_reported_as_duplicate_version(ver_api):
    client, db, headers, _ids = ver_api
    before = snapshot(db)
    error = IntegrityError("insert audit", {}, Exception("foreign key failure"))
    with patch.object(AuditService, "log", side_effect=error):
        response = client.post(
            "/api/v1/versions",
            headers=headers["alice"],
            json={"system_id": 1, "version_no": "NOT-DUPLICATE", "name": "版本"},
        )
    assert response.status_code == 500
    assert response.json()["code"] != 40934
    assert snapshot(db) == before


@pytest.mark.parametrize(
    "state,key,errno,message,expected",
    [
        ("23505", "ix_rd_version_version_no", None, "", True),
        ("23505", "rd_version_pkey", None, "", False),
        ("23503", "ix_rd_version_version_no", None, "", False),
        (None, None, 1062, "Duplicate entry 'x' for key 'ix_rd_version_version_no'", True),
        (
            None,
            None,
            1062,
            "Duplicate entry 'x' for key 'rd_version.ix_rd_version_version_no'",
            True,
        ),
        (None, None, 1062, "Duplicate entry 'x' for key 'PRIMARY'", False),
        (None, None, 1452, "Cannot add or update child row", False),
    ],
)
def test_duplicate_classifier_only_accepts_exact_version_number_constraint(
    state, key, errno, message, expected
):
    original = Exception(errno, message)
    original.sqlstate = state
    original.diag = SimpleNamespace(constraint_name=key)
    assert (
        VersionService._is_version_no_unique_conflict(IntegrityError("insert", {}, original))
        is expected
    )

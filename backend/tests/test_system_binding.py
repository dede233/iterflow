"""Single-system ownership through normal APIs, using new temporary SQLite databases."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_entity_actions import actions_api as actions_api
from test_entity_actions import req
from test_version_progress import progress_api as progress_api

from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    OperationLog,
    Release,
    Version,
    VersionRequirement,
)


@pytest.fixture
def binding_api(progress_api):
    client, db, headers, users = progress_api
    db.add_all(
        [
            BusinessSystem(id=101, code="A", name="系统甲"),
            BusinessSystem(id=102, code="B", name="系统乙"),
            BusinessSystem(id=103, code="OFF", name="停用系统", enabled=False),
        ]
    )
    db.flush()
    db.add(BusinessModule(id=101, system_id=101, code="M", name="模块甲"))
    db.commit()
    return client, db, headers, users


def create_version(client, headers, system_id=101, **extra):
    return client.post(
        "/api/v1/versions",
        headers=headers,
        json={
            "system_id": system_id,
            "name": "绑定测试版本",
            "version_no": str(uuid4())[:24],
            **extra,
        },
    )


def test_create_validation_options_and_filters(binding_api):
    client, db, headers, users = binding_api
    assert create_version(client, headers["boss"], None).status_code == 422
    assert create_version(client, headers["boss"], 99999).status_code == 422
    assert create_version(client, headers["boss"], 103).status_code == 422
    response = create_version(client, headers["boss"])
    assert response.status_code == 200, response.text
    assert response.json()["system_name"] == "系统甲"
    options = client.get("/api/v1/systems/options", headers=headers["boss"])
    assert options.status_code == 200
    assert {o["id"] for o in options.json()} >= {101, 102}
    assert 103 not in {o["id"] for o in options.json()}
    assert all(set(o) == {"id", "name"} for o in options.json())
    assert client.get("/api/v1/systems/options").status_code == 401
    assert (
        client.get("/api/v1/versions", headers=headers["boss"], params={"system_id": 102}).json()[
            "total"
        ]
        == 0
    )
    item = req(db, users["alice"], "system-filter", system_id=101)
    assert (
        client.get(
            "/api/v1/requirements", headers=headers["boss"], params={"system_id": 101}
        ).json()["items"][0]["id"]
        == item.id
    )
    assert (
        client.get(
            "/api/v1/requirements", headers=headers["bob"], params={"system_id": 101}
        ).json()["total"]
        == 0
    )


@pytest.mark.parametrize(
    "system_id,module_id", [(99999, None), (103, None), (102, 101), (None, 101)]
)
def test_requirement_rejects_invalid_directory(binding_api, system_id, module_id):
    client, _db, headers, _users = binding_api
    response = client.post(
        "/api/v1/requirements",
        headers=headers["boss"],
        json={
            "title": "系统绑定需求",
            "description": "完整的需求内容",
            "requirement_type": "FEATURE",
            "system_id": system_id,
            "module_id": module_id,
        },
    )
    assert response.status_code == 422, response.text


def test_association_edit_move_and_cas(binding_api):
    client, db, headers, users = binding_api
    item = req(db, users["boss"], "association", system_id=101)
    version = create_version(client, headers["boss"]).json()
    other = create_version(client, headers["boss"], 102).json()
    payload = {
        "requirement_id": item.id,
        "revision": item.revision,
        "version_revision": other["revision"],
    }
    assert (
        client.post(
            f"/api/v1/versions/{other['id']}/requirements", headers=headers["boss"], json=payload
        ).status_code
        == 409
    )
    payload["version_revision"] = version["revision"]
    response = client.post(
        f"/api/v1/versions/{version['id']}/requirements", headers=headers["boss"], json=payload
    )
    assert response.status_code == 200, response.text
    db.refresh(item)
    assert (
        client.patch(
            f"/api/v1/requirements/{item.id}",
            headers=headers["boss"],
            json={"revision": item.revision, "system_id": 102},
        ).status_code
        == 409
    )
    version = response.json()
    assert (
        client.patch(
            f"/api/v1/versions/{version['id']}",
            headers=headers["boss"],
            json={"revision": version["revision"], "system_id": 102},
        ).status_code
        == 409
    )
    payload.update(
        revision=item.revision, version_revision=other["revision"], reason="移动到其他版本"
    )
    assert (
        client.post(
            f"/api/v1/versions/{other['id']}/requirements/move",
            headers=headers["boss"],
            json=payload,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/versions/{version['id']}",
            headers=headers["boss"],
            json={"revision": version["revision"] - 1, "system_id": 101},
        ).status_code
        == 409
    )
    db.refresh(item)
    assert item.system_id == 101 and item.current_version_id == version["id"]
    assert db.scalar(select(func.count()).select_from(VersionRequirement)) == 1


def test_create_and_bulk_association_atomic(binding_api):
    client, db, headers, users = binding_api
    good = req(db, users["boss"], "good", system_id=101)
    bad = req(db, users["boss"], "bad", system_id=102)
    before = db.scalar(select(func.count()).select_from(Version))
    response = create_version(
        client, headers["boss"], requirement_id=bad.id, requirement_revision=bad.revision
    )
    assert response.status_code == 409
    assert db.scalar(select(func.count()).select_from(Version)) == before
    version = create_version(client, headers["boss"]).json()
    response = client.post(
        f"/api/v1/versions/{version['id']}/requirements/batch",
        headers=headers["boss"],
        json={
            "version_revision": version["revision"],
            "request_id": str(uuid4()),
            "items": [{"requirement_id": r.id, "revision": r.revision} for r in [good, bad]],
        },
    )
    assert response.status_code == 409, response.text
    assert db.scalar(select(func.count()).select_from(VersionRequirement)) == 0
    response = create_version(
        client, headers["boss"], requirement_id=good.id, requirement_revision=good.revision
    )
    assert response.status_code == 200, response.text
    assert response.json()["system_id"] == 101


def test_legacy_repair_and_publish_gate(binding_api):
    client, db, headers, users = binding_api
    old = Version(version_no="LEGACY", name="历史版本", created_by=users["boss"].id)
    db.add(old)
    db.flush()
    item = req(
        db, users["boss"], "legacy", current_version_id=old.id, status="DONE", legacy_completed=True
    )
    db.add(VersionRequirement(version_id=old.id, requirement_id=item.id, added_by=users["boss"].id))
    db.commit()
    check = client.post(f"/api/v1/versions/{old.id}/publish/check", headers=headers["boss"]).json()
    assert check["code"] == 40923
    assert any(
        c["type"] == "SYSTEM_BINDING_CHECK" and not c["passed"] for c in check["data"]["checks"]
    )
    assert (
        client.post(
            f"/api/v1/versions/{old.id}/publish",
            headers=headers["boss"],
            json={
                "revision": old.revision,
                "released_at": datetime.now(UTC).isoformat(),
                "release_notes": "不应发布",
            },
        ).status_code
        == 409
    )
    assert db.scalar(select(func.count()).select_from(Release)) == 0
    assert (
        client.patch(
            f"/api/v1/versions/{old.id}",
            headers=headers["boss"],
            json={"revision": old.revision, "system_id": 101},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/requirements/{item.id}",
            headers=headers["boss"],
            json={"revision": item.revision, "system_id": 101},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/versions/{old.id}",
            headers=headers["boss"],
            json={"revision": old.revision, "system_id": 101},
        ).status_code
        == 200
    )
    check = client.post(f"/api/v1/versions/{old.id}/publish/check", headers=headers["boss"]).json()
    assert check["passed"], check


def test_central_submit_mismatch_has_no_writes(binding_api):
    client, db, headers, users = binding_api
    version = create_version(client, headers["boss"]).json()
    item = req(
        db,
        users["boss"],
        "mismatch",
        system_id=102,
        current_version_id=version["id"],
        status="CONFIRMED",
        legacy_completed=True,
    )
    db.add(
        VersionRequirement(
            version_id=version["id"], requirement_id=item.id, added_by=users["boss"].id
        )
    )
    db.commit()
    before = db.scalar(select(func.count()).select_from(OperationLog))
    response = client.post(
        f"/api/v1/versions/{version['id']}/requirements/submit-acceptance",
        headers=headers["boss"],
        json={
            "version_revision": version["revision"],
            "reason": "开发已经完成",
            "items": [{"id": item.id, "revision": item.revision}],
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert not result["success"] and result["code"] == 40975, result
    db.refresh(item)
    assert item.status == "CONFIRMED"
    assert db.scalar(select(func.count()).select_from(OperationLog)) == before

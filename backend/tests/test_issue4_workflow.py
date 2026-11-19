"""Normal API coverage with a new temporary SQLite database per test."""

import pytest
from sqlalchemy import func, select
from test_requirement_api import _create_req
from test_requirement_api import req_api as req_api

from app.models.entities import (
    CollaborationEvent,
    OperationLog,
    Requirement,
    RequirementParticipant,
    RequirementStep,
    Role,
    User,
    Version,
)
from app.models.enums import RequirementStatus, UserStatus, VersionStatus


@pytest.mark.parametrize("legacy_status_route", [False, True])
def test_confirmation_waits_for_development_and_acceptance(req_api, legacy_status_route):
    client, db, headers, ids = req_api
    actor = headers["alice"]
    confirmer = {"role": "CONFIRM", "user_id": ids["alice"]}
    item = _create_req(client, actor, participants=[confirmer])
    path = f"/api/v1/requirements/{item['id']}"

    def confirm(revision):
        if legacy_status_route:
            return client.patch(
                path + "/status", headers=actor, json={"status": "CONFIRMED", "revision": revision}
            )
        return client.post(
            path + "/workflow", headers=actor, json={"action": "CONFIRM", "revision": revision}
        )

    tracked = (RequirementStep, OperationLog, CollaborationEvent)
    before = [db.scalar(select(func.count()).select_from(model)) for model in tracked]
    rejected = confirm(item["revision"])
    assert rejected.status_code == 409 and rejected.json()["code"] == 40961
    assert "开发人员和验收人员" in rejected.json()["message"]
    db.expire_all()
    stored = db.get(Requirement, item["id"])
    assert stored.status == "DRAFT" and stored.revision == item["revision"]
    assert stored.confirmed_revision is None
    assert [db.scalar(select(func.count()).select_from(model)) for model in tracked] == before

    assigned = client.put(
        path + "/participants",
        headers=actor,
        json={
            "revision": item["revision"],
            "participants": [
                confirmer,
                {"role": "DEVELOP", "user_id": ids["bob"]},
                {"role": "ACCEPT", "user_id": ids["bob"]},
            ],
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert client.get(path, headers=actor).json()["status"] == "DRAFT"
    confirmed = confirm(assigned.json()["revision"])
    assert confirmed.status_code == 200, confirmed.text
    assert client.get(path, headers=actor).json()["status"] == "CONFIRMED"
    record = db.scalar(select(RequirementStep))
    assert record.actor_id == ids["alice"]
    assert {p["role"] for p in record.detail["participants"]} == {"CONFIRM", "DEVELOP", "ACCEPT"}


@pytest.mark.parametrize("role, label", [("DEVELOP", "开发人员"), ("ACCEPT", "验收人员")])
def test_reconfirmation_requires_active_people_and_preserves_stage(req_api, role, label):
    client, db, headers, ids = req_api
    actor = headers["boss"]
    participants = [
        {"role": "CONFIRM", "user_id": ids["boss"]},
        {"role": "DEVELOP", "user_id": ids["boss"]},
        {"role": "ACCEPT", "user_id": ids["bob"]},
    ]
    item = _create_req(client, actor, participants=participants)
    path = f"/api/v1/requirements/{item['id']}"

    def confirm(revision):
        return client.post(
            path + "/workflow", headers=actor, json={"action": "CONFIRM", "revision": revision}
        )

    first = confirm(item["revision"])
    assert first.status_code == 200, first.text
    started = client.patch(
        path + "/status",
        headers=actor,
        json={"revision": first.json()["revision"], "status": "DEVELOPING"},
    )
    assert started.status_code == 200, started.text
    edited = client.patch(
        path, headers=actor, json={"revision": started.json()["revision"], "description": "新范围"}
    )
    assert edited.status_code == 200, edited.text
    revision = edited.json()["revision"]
    if role == "DEVELOP":
        assignment = db.scalar(
            select(RequirementParticipant).where(
                RequirementParticipant.requirement_id == item["id"],
                RequirementParticipant.role == "DEVELOP",
            )
        )
        assert assignment is not None
        assignment.active = False
    else:
        acceptor = db.get(User, ids["bob"])
        acceptor.status = UserStatus.DISABLED
    db.commit()
    rejected = confirm(revision)
    assert rejected.status_code == 409 and label in rejected.json()["message"]
    assert client.get(path, headers=actor).json()["revision"] == revision
    view = client.get(path + "/workflow", headers=actor).json()
    assert view["needs_confirmation"]
    assert [record["action"] for record in view["records"]].count("CONFIRM") == 1

    next(person for person in participants if person["role"] == role)["user_id"] = ids["alice"]
    assigned = client.put(
        path + "/participants",
        headers=actor,
        json={"revision": revision, "participants": participants},
    )
    assert assigned.status_code == 200, assigned.text
    confirmed = confirm(assigned.json()["revision"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["needs_confirmation"] is False
    assert client.get(path, headers=actor).json()["status"] == "DEVELOPING"


def test_multiple_confirmers_single_confirmation_and_stale_revision(req_api):
    client, db, headers, ids = req_api
    item = _create_req(
        client,
        headers["boss"],
        participants=[
            {"role": "CONFIRM", "user_id": ids["alice"]},
            {"role": "CONFIRM", "user_id": ids["bob"]},
            {"role": "DEVELOP", "user_id": ids["alice"]},
            {"role": "ACCEPT", "user_id": ids["bob"]},
        ],
    )
    path = f"/api/v1/requirements/{item['id']}/workflow"
    payload = {"action": "CONFIRM", "revision": item["revision"]}
    assert client.post(path, headers=headers["reader"], json=payload).status_code == 403
    assert client.post(path, headers=headers["bob"], json=payload).status_code == 200
    assert client.post(path, headers=headers["alice"], json=payload).status_code == 409
    latest = client.get(f"/api/v1/requirements/{item['id']}", headers=headers["boss"]).json()
    assert latest["status"] == "CONFIRMED"
    assert len(list(db.scalars(select(RequirementStep)))) == 1
    record = db.scalar(select(RequirementStep))
    assert record.actor_id == ids["bob"]
    assert record.detail["description_format"] == "PLAIN"


def test_reopen_clears_confirmation_keeps_people_and_requires_reason(req_api):
    client, db, headers, _ids = req_api
    item = _create_req(client, headers["boss"])
    row = db.get(Requirement, item["id"])
    row.status = RequirementStatus.CANCELED
    row.confirmed_revision = row.content_revision
    row.legacy_completed = True
    row.paused_from = "DEVELOPING"
    db.commit()
    people_before = list(db.scalars(select(RequirementParticipant)))
    path = f"/api/v1/requirements/{item['id']}/workflow"
    payload = {"action": "REOPEN", "revision": item["revision"]}
    assert client.post(path, headers=headers["reader"], json=payload).status_code == 403
    assert client.post(path, headers=headers["boss"], json=payload).status_code == 422
    result = client.post(path, headers=headers["boss"], json={**payload, "reason": "重新评估需求"})
    assert result.status_code == 200, result.text
    db.refresh(row)
    assert row.status == RequirementStatus.DRAFT
    assert row.confirmed_revision is None and not row.legacy_completed and row.paused_from is None
    assert row.revision == item["revision"] + 1
    assert list(db.scalars(select(RequirementParticipant))) == people_before
    assert (
        client.post(path, headers=headers["boss"], json={**payload, "reason": "旧请求"}).status_code
        == 409
    )
    assert len(list(db.scalars(select(RequirementStep)))) == 1
    assert db.scalar(select(RequirementStep)).detail["reason"] == "重新评估需求"


def test_reopen_rejects_online_and_released_version(req_api):
    client, db, headers, _ids = req_api
    item = _create_req(client, headers["boss"])
    row = db.get(Requirement, item["id"])
    path = f"/api/v1/requirements/{item['id']}/workflow"
    payload = {"action": "REOPEN", "revision": item["revision"], "reason": "重开检查"}
    row.status = RequirementStatus.ONLINE
    db.commit()
    assert client.post(path, headers=headers["boss"], json=payload).status_code == 409
    Version.__table__.create(db.get_bind(), checkfirst=True)
    version = Version(
        id=99, version_no="V-RELEASED", name="已发布版本", status=VersionStatus.RELEASED
    )
    db.add(version)
    db.flush()
    row.status = RequirementStatus.CANCELED
    row.current_version_id = version.id
    db.commit()
    response = client.post(path, headers=headers["boss"], json=payload)
    assert response.status_code == 409, response.text
    assert "已发布版本" in response.json()["message"]
    assert not list(db.scalars(select(RequirementStep)))


def _start_development(client, actor, requirement):
    path = f"/api/v1/requirements/{requirement['id']}"
    confirmed = client.post(
        path + "/workflow",
        headers=actor,
        json={"action": "CONFIRM", "revision": requirement["revision"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    started = client.patch(
        path + "/status",
        headers=actor,
        json={"status": "DEVELOPING", "revision": confirmed.json()["revision"]},
    )
    assert started.status_code == 200, started.text
    return path, started.json()["revision"]


def test_complete_and_accept_requires_both_roles_and_disallows_delegation(req_api):
    client, db, headers, ids = req_api
    admin_role = db.scalar(select(Role).where(Role.code == "ALLROLE"))
    admin_role.code = "SUPER_ADMIN"
    admin_role.is_system = True
    db.commit()
    people = [
        {"role": "CONFIRM", "user_id": ids["alice"]},
        {"role": "DEVELOP", "user_id": ids["alice"]},
        {"role": "ACCEPT", "user_id": ids["bob"]},
        {"role": "DEVELOP", "user_id": ids["reader"]},
        {"role": "ACCEPT", "user_id": ids["reader"]},
    ]
    item = _create_req(client, headers["alice"], participants=people)
    path, revision = _start_development(client, headers["alice"], item)
    payload = {"action": "COMPLETE_AND_ACCEPT", "revision": revision, "reason": "代操作说明"}
    tracked = (RequirementStep, OperationLog, CollaborationEvent)
    before = [db.scalar(select(func.count()).select_from(model)) for model in tracked]

    for user in ("alice", "bob", "boss", "reader"):
        rejected = client.post(path + "/workflow", headers=headers[user], json=payload)
        assert rejected.status_code == 403, rejected.text
    stored = client.get(path, headers=headers["alice"]).json()
    assert stored["status"] == "DEVELOPING" and stored["revision"] == revision
    assert [db.scalar(select(func.count()).select_from(model)) for model in tracked] == before

    people.append({"role": "ACCEPT", "user_id": ids["alice"]})
    assigned = client.put(
        path + "/participants",
        headers=headers["alice"],
        json={"revision": revision, "participants": people},
    )
    assert assigned.status_code == 200, assigned.text
    revision = assigned.json()["revision"]
    participant = db.get(RequirementParticipant, (item["id"], ids["alice"], "ACCEPT"))
    participant.active = False
    db.commit()
    rejected = client.post(
        path + "/workflow", headers=headers["alice"], json={**payload, "revision": revision}
    )
    assert rejected.status_code == 403, rejected.text

    unrelated = _create_req(client, headers["alice"])
    other_path, other_revision = _start_development(client, headers["alice"], unrelated)
    out_of_scope = client.post(
        other_path + "/workflow",
        headers=headers["bob"],
        json={**payload, "revision": other_revision},
    )
    assert out_of_scope.status_code == 404, out_of_scope.text


def test_complete_and_accept_respects_stage_content_design_and_release_freeze(req_api):
    client, db, headers, ids = req_api
    actor = headers["alice"]
    item = _create_req(
        client,
        actor,
        participants=[
            {"role": role, "user_id": ids["alice"]}
            for role in ("CONFIRM", "DEVELOP", "ACCEPT", "DESIGN")
        ],
    )
    path = f"/api/v1/requirements/{item['id']}"

    def workflow(action, revision):
        return client.post(
            path + "/workflow", headers=actor, json={"action": action, "revision": revision}
        )

    rejected = workflow("COMPLETE_AND_ACCEPT", item["revision"])
    assert rejected.status_code == 409 and "开发中" in rejected.json()["message"]
    _, revision = _start_development(client, actor, item)
    updated = client.patch(
        path, headers=actor, json={"description": "调整需求内容", "revision": revision}
    )
    assert updated.status_code == 200, updated.text
    revision = updated.json()["revision"]
    rejected = workflow("COMPLETE_AND_ACCEPT", revision)
    assert rejected.status_code == 409 and "尚未确认" in rejected.json()["message"]
    for action in ("CONFIRM", "DESIGN_PENDING"):
        changed = workflow(action, revision)
        assert changed.status_code == 200, changed.text
        revision = changed.json()["revision"]
    rejected = workflow("COMPLETE_AND_ACCEPT", revision)
    assert rejected.status_code == 409 and "先完成设计" in rejected.json()["message"]
    for action in ("DESIGN_START", "DESIGN_DONE"):
        changed = workflow(action, revision)
        assert changed.status_code == 200, changed.text
        revision = changed.json()["revision"]

    version = Version(id=99, version_no="V-FROZEN", name="冻结版本", release_frozen=True)
    db.add(version)
    db.flush()
    stored = db.get(Requirement, item["id"])
    stored.current_version_id = version.id
    db.commit()
    blocked = workflow("COMPLETE_AND_ACCEPT", revision)
    assert blocked.status_code == 409 and blocked.json()["code"] == 40986
    db.refresh(stored)
    assert stored.revision == revision and stored.status == "DEVELOPING"
    version.release_frozen = False
    db.commit()

    completed = workflow("COMPLETE_AND_ACCEPT", revision)
    assert completed.status_code == 200, completed.text
    assert completed.json()["revision"] == revision + 1
    assert client.get(path, headers=actor).json()["status"] == "DONE"

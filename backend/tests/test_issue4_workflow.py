"""Normal API coverage with a new temporary SQLite database per test."""

from sqlalchemy import select
from test_requirement_api import _create_req
from test_requirement_api import req_api as req_api

from app.models.entities import Requirement, RequirementParticipant, RequirementStep, Version
from app.models.enums import RequirementStatus, VersionStatus


def test_multiple_confirmers_single_confirmation_and_stale_revision(req_api):
    client, db, headers, ids = req_api
    item = _create_req(
        client,
        headers["boss"],
        participants=[
            {"role": "CONFIRM", "user_id": ids["alice"]},
            {"role": "CONFIRM", "user_id": ids["bob"]},
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

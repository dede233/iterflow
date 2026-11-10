"""Deletion/association races on independently created real-database fixtures."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from app.core.exceptions import AppError
from app.models.entities import (
    Feedback,
    OperationLog,
    Requirement,
    RequirementFeedback,
    VersionRequirement,
)
from app.models.enums import DataScope
from app.schemas.entity_actions import EntityDelete
from app.schemas.feedback import FeedbackConvertRequest
from app.schemas.version import AddRequirementRequest
from app.services.entity_actions_service import EntityActionsService
from app.services.feedback_service import FeedbackService
from app.services.version_service import VersionService


def exercise_actions(fixture, scenario, monkeypatch):
    client, engine, uid, headers = fixture
    system_id = create_test_system(engine)
    response = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "title": "隔离删除测试",
            "description": "需求范围",
            "requirement_type": "FEATURE",
            "system_id": system_id,
            "participants": [{"user_id": uid, "role": "CONFIRM"}],
        },
    )
    assert response.status_code == 200, response.text
    requirement = response.json()
    response = client.post(
        "/api/v1/feedbacks",
        headers=headers,
        json={
            "title": "隔离删除反馈",
            "description": "反馈内容",
            "feedback_type": "OTHER",
            "recipient_ids": [uid],
        },
    )
    assert response.status_code == 200, response.text
    feedback = response.json()
    if scenario == "batch":
        response = client.post(
            "/api/v1/requirements/batch-actions",
            headers=headers,
            json={
                "action": "CONFIRM",
                "items": [
                    {"id": requirement["id"], "revision": 1},
                    {"id": 9999999, "revision": 1},
                ],
            },
        )
        assert response.status_code == 200, response.text
        assert [r["status_code"] for r in response.json()["results"]] == [200, 404]
        response = client.post(
            "/api/v1/requirements/batch-actions",
            headers=headers,
            json={
                "action": "CONFIRM",
                "items": [{"id": requirement["id"], "revision": 1}],
            },
        )
        assert response.json()["results"][0]["status_code"] == 409
        return
    if scenario == "rollback":

        def fail(*_args, **_kwargs):
            raise RuntimeError("isolated audit failure")

        monkeypatch.setattr("app.services.audit_service.AuditService.log", fail)
        with Session(engine) as db:
            try:
                EntityActionsService(db).delete(
                    "requirement",
                    requirement["id"],
                    EntityDelete(revision=1, reason="误建删除"),
                    uid,
                )
                raise AssertionError("expected audit failure")
            except RuntimeError:
                db.rollback()
        with Session(engine) as db:
            stored = db.get(Requirement, requirement["id"])
            assert stored.deleted_at is None and stored.revision == 1
        return
    version = None
    if scenario == "version_race":
        response = client.post(
            "/api/v1/versions",
            headers=headers,
            json={
                "system_id": system_id,
                "version_no": "V-ISSUE4-RACE",
                "name": "隔离版本",
                "owner_id": uid,
            },
        )
        assert response.status_code == 200, response.text
        version = response.json()
    barrier = Barrier(2)
    kind = "feedback" if scenario == "convert_race" else "requirement"
    entity_id = feedback["id"] if kind == "feedback" else requirement["id"]

    def run(delete):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                if delete:
                    EntityActionsService(db).delete(
                        kind, entity_id, EntityDelete(revision=1, reason="误建删除"), uid
                    )
                    return "deleted"
                if scenario == "delete_race":
                    EntityActionsService(db).delete(
                        kind, entity_id, EntityDelete(revision=1, reason="重复删除"), uid
                    )
                    return "deleted"
                if scenario == "version_race":
                    VersionService(db).add_requirement(
                        version["id"],
                        AddRequirementRequest(
                            requirement_id=requirement["id"],
                            revision=1,
                            version_revision=1,
                        ),
                        uid,
                        viewer_scope=DataScope.ALL,
                        viewer_id=uid,
                    )
                else:
                    FeedbackService(db).convert(
                        feedback["id"],
                        FeedbackConvertRequest(
                            type="LINK_EXISTING",
                            requirement_id=requirement["id"],
                            revision=1,
                        ),
                        uid,
                        viewer_scope=DataScope.ALL,
                        viewer_id=uid,
                    )
                return "linked"
            except AppError:
                db.rollback()
                return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, [True, False]))
    assert outcomes.count("blocked") == 1, outcomes
    with Session(engine) as db:
        stored = db.get(Feedback if kind == "feedback" else Requirement, entity_id)
        relations = db.scalar(
            select(func.count()).select_from(
                VersionRequirement if scenario == "version_race" else RequirementFeedback
            )
        )
        if "deleted" in outcomes:
            assert stored.deleted_at is not None and stored.revision == 2 and relations == 0
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(OperationLog)
                    .where(OperationLog.action == "SOFT_DELETE")
                )
                == 1
            )
        else:
            assert stored.deleted_at is None and relations == 1

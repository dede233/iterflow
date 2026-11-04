"""Atomic version creation and concurrency gates for newly isolated real databases."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import (
    CollaborationEvent,
    OperationLog,
    Requirement,
    User,
    Version,
    VersionRequirement,
)
from app.schemas.entity_actions import EntityDelete
from app.schemas.version import VersionCreate
from app.services.audit_service import AuditService
from app.services.entity_actions_service import EntityActionsService
from app.services.version_service import VersionService


def exercise_version_entry(fixture, scenario, monkeypatch):
    client, engine, uid, headers = fixture
    response = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "title": "新建版本关联需求",
            "description": "隔离验收内容",
            "requirement_type": "FEATURE",
        },
    )
    assert response.status_code == 200, response.text
    requirement = response.json()
    linked = VersionCreate(
        version_no="ENTRY-LINK",
        name="需求入口版本",
        requirement_id=requirement["id"],
        requirement_revision=requirement["revision"],
    )
    if scenario == "success":
        with Session(engine, expire_on_commit=False) as db:
            owner = User(
                username="version-entry-owner", display_name="版本负责人", password_hash="unused"
            )
            db.add(owner)
            db.commit()
            owner_id = owner.id
        linked = linked.model_copy(update={"owner_id": owner_id})
        response = client.post("/api/v1/versions", headers=headers, json=linked.model_dump())
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 2 and response.json()["status"] == "PLANNING"
        with Session(engine) as db:
            item = db.get(Requirement, requirement["id"])
            assert item.revision == 2 and item.current_version_id == response.json()["id"]
            assert db.scalar(select(func.count()).select_from(VersionRequirement)) == 1
            event = db.scalar(
                select(CollaborationEvent).where(CollaborationEvent.action == "RELATION_CHANGE")
            )
            assert owner_id in event.recipient_ids
        duplicate = client.post("/api/v1/versions", headers=headers, json=linked.model_dump())
        assert duplicate.status_code == 409 and duplicate.json()["code"] == 40934
        return
    if scenario == "rollback":
        original = AuditService.log

        def fail(self, *args, **kwargs):
            if args[2] == "VERSION_REQUIREMENT_ADD":
                raise RuntimeError("isolated relation audit failure")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(AuditService, "log", fail)
        with Session(engine) as db:
            try:
                VersionService(db).create(linked, uid)
            except RuntimeError:
                pass
            else:
                raise AssertionError("expected audit failure")
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Version)) == 0
            assert db.scalar(select(func.count()).select_from(VersionRequirement)) == 0
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(OperationLog)
                    .where(OperationLog.entity_type == "VERSION")
                )
                == 0
            )
            item = db.get(Requirement, requirement["id"])
            assert item.revision == 1 and item.current_version_id is None
        return
    if scenario == "unrelated_integrity":
        with Session(engine) as db:
            try:
                VersionService(db).create(
                    VersionCreate(version_no="ENTRY-FK", name="非法负责人", owner_id=99999999), uid
                )
            except IntegrityError:
                pass
            else:
                raise AssertionError("foreign-key failure must remain an IntegrityError")
            assert db.scalar(select(func.count()).select_from(Version)) == 0
        return
    barrier = Barrier(2)
    if scenario == "duplicate_race":
        original_check = VersionService._version_no_exists

        def simultaneous_check(self, version_no):
            existing = original_check(self, version_no)
            barrier.wait(timeout=10)
            return existing

        monkeypatch.setattr(VersionService, "_version_no_exists", simultaneous_check)

    def run(index):
        with Session(engine, expire_on_commit=False) as db:
            try:
                if scenario != "duplicate_race":
                    barrier.wait(timeout=10)
                if scenario == "delete_race" and index == 1:
                    EntityActionsService(db).delete(
                        "requirement",
                        requirement["id"],
                        EntityDelete(revision=1, reason="重复需求"),
                        uid,
                    )
                else:
                    payload = (
                        VersionCreate(version_no="ENTRY-DUP", name="并发同号")
                        if scenario == "duplicate_race"
                        else linked.model_copy(update={"version_no": f"ENTRY-{index}"})
                    )
                    VersionService(db).create(payload, uid)
                return 200, 0
            except AppError as error:
                db.rollback()
                return error.status_code, error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [0, 1]))
    with Session(engine) as db:
        versions = db.scalar(select(func.count()).select_from(Version))
        relations = db.scalar(select(func.count()).select_from(VersionRequirement))
        creates = db.scalar(
            select(func.count())
            .select_from(OperationLog)
            .where(OperationLog.entity_type == "VERSION", OperationLog.action == "CREATE")
        )
        item = db.get(Requirement, requirement["id"])
        if scenario == "duplicate_race":
            assert sorted(results) == [(200, 0), (409, 40934)]
            assert versions == creates == 1 and relations == 0
        elif scenario == "relation_race":
            assert sorted(results) == [(200, 0), (409, 40910)]
            assert versions == creates == relations == 1
            assert item.revision == 2 and item.current_version_id is not None
        else:
            assert scenario == "delete_race"
            assert sum(status == 200 for status, _ in results) == 1
            assert all(status in {200, 404, 409} for status, _ in results)
            if item.deleted_at is not None:
                assert versions == creates == relations == 0
            else:
                assert versions == creates == relations == 1
                assert item.current_version_id is not None

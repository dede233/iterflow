"""Issue 4 confirmation races and migration preservation on fresh SQL fixtures."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.security import create_access_token
from app.models.entities import CollaborationEvent, Requirement, RequirementStep, User, UserRole


def exercise_issue4(fixture, scenario):
    client, engine, uid, headers = fixture
    with Session(engine) as db:
        other = User(
            username="issue4-confirmer",
            display_name="第二确认人",
            password_hash="unused",
            must_change_password=False,
        )
        db.add(other)
        db.flush()
        role_id = db.scalar(select(UserRole.role_id).where(UserRole.user_id == uid))
        db.add(UserRole(user_id=other.id, role_id=role_id))
        db.commit()
        other_id = other.id
    people = [{"user_id": uid, "role": "CONFIRM"}]
    if scenario == "race":
        people.append({"user_id": other_id, "role": "CONFIRM"})
    response = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "title": "多人确认与迁移",
            "requirement_type": "FEATURE",
            "description": "保留原文本 <b>原样</b>",
            "description_format": "PLAIN",
            "participants": people,
        },
    )
    assert response.status_code == 200, response.text
    item = response.json()
    rid = item["id"]
    path = f"/api/v1/requirements/{rid}/workflow"
    if scenario == "race":
        barrier = Barrier(2)
        actors = [headers, {"Authorization": "Bearer " + create_access_token(other_id)}]

        def confirm(actor):
            barrier.wait()
            return client.post(path, headers=actor, json={"action": "CONFIRM", "revision": 1})

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, actors))
        assert sorted(result.status_code for result in results) == [200, 409]
        with Session(engine) as db:
            row = db.get(Requirement, rid)
            assert row.status == "CONFIRMED" and row.revision == 2
            records = list(
                db.scalars(select(RequirementStep).where(RequirementStep.requirement_id == rid))
            )
            assert len(records) == 1 and records[0].actor_id in {uid, other_id}
            created = db.scalar(
                select(CollaborationEvent).where(
                    CollaborationEvent.entity_id == rid, CollaborationEvent.action == "CREATED"
                )
            )
            assert set(created.recipient_ids) >= {uid, other_id}
        canceled = client.patch(
            f"/api/v1/requirements/{rid}/status",
            headers=headers,
            json={"status": "CANCELED", "revision": 2, "reason": "暂停范围"},
        )
        assert canceled.status_code == 200, canceled.text
        reopened = client.post(
            path,
            headers=headers,
            json={"action": "REOPEN", "revision": 3, "reason": "重新评估范围"},
        )
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["needs_confirmation"]
        with Session(engine) as db:
            assert db.get(Requirement, rid).status == "DRAFT"
            assert (
                len(
                    list(
                        db.scalars(
                            select(RequirementStep).where(RequirementStep.requirement_id == rid)
                        )
                    )
                )
                == 3
            )
        return

    mysql = engine.dialect.name == "mysql"
    config = Config(
        str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
    )
    previous = "mysql57_0011" if mysql else "0013_mail_notice"
    command.downgrade(config, previous)
    with engine.connect() as db:
        before = dict(
            db.execute(text("SELECT * FROM rd_requirement WHERE id=:rid"), {"rid": rid})
            .mappings()
            .one()
        )
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as db:
        after = dict(
            db.execute(text("SELECT * FROM rd_requirement WHERE id=:rid"), {"rid": rid})
            .mappings()
            .one()
        )
    assert {
        key: value
        for key, value in after.items()
        if key not in {"description_format", "deleted_at", "deleted_by"}
    } == before
    assert (
        after["description_format"] == "PLAIN"
        and after["deleted_at"] is None
        and after["deleted_by"] is None
    )
    if scenario == "migration_plain":
        command.downgrade(config, previous)
        command.upgrade(config, "head")
        return
    with engine.begin() as db:
        if scenario == "migration_format":
            db.execute(
                text("UPDATE rd_requirement SET description_format='HTML' WHERE id=:rid"),
                {"rid": rid},
            )
        elif scenario == "migration_deleted":
            db.execute(
                text(
                    "UPDATE rd_requirement SET deleted_at=CURRENT_TIMESTAMP,deleted_by=:uid "
                    "WHERE id=:rid"
                ),
                {"rid": rid, "uid": uid},
            )
        elif scenario == "migration_multiple":
            db.execute(
                text(
                    "INSERT INTO rd_requirement_actor (requirement_id,user_id,role,active) "
                    "VALUES (:rid,:uid,'CONFIRM',true)"
                ),
                {"rid": rid, "uid": other_id},
            )
    with pytest.raises(RuntimeError, match="refuse lossy downgrade"):
        command.downgrade(config, previous)
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == (
            "mysql57_0012" if mysql else "0016_announcements"
        )

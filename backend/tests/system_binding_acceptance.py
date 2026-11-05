"""Same ownership, migration and lock-race checks on PostgreSQL and MySQL."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from alembic import command
from app.core.exceptions import AppError
from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import DataScope
from app.schemas.requirement import RequirementUpdate
from app.schemas.version import AddRequirementRequest
from app.services.requirement_service import RequirementService
from app.services.version_service import VersionService


def exercise_binding(fixture, scenario):
    client, engine, uid, headers = fixture
    first, second = create_test_system(engine), create_test_system(engine)
    r = client.post(
        "/api/v1/requirements",
        headers=headers,
        json={
            "title": "系统绑定验收",
            "description": "隔离数据库验收内容",
            "requirement_type": "FEATURE",
            "system_id": first,
        },
    )
    assert r.status_code == 200, r.text
    req = r.json()
    v = client.post(
        "/api/v1/versions",
        headers=headers,
        json={"version_no": "BIND-REAL", "name": "系统绑定版本", "system_id": first},
    )
    assert v.status_code == 200, v.text
    ver = v.json()
    if scenario == "race":
        barrier = Barrier(2)

        def attach():
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    VersionService(db).add_requirement(
                        ver["id"],
                        AddRequirementRequest(
                            requirement_id=req["id"],
                            revision=req["revision"],
                            version_revision=ver["revision"],
                        ),
                        uid,
                        DataScope.ALL,
                        uid,
                    )
                    return "ok"
                except AppError:
                    db.rollback()
                    return "blocked"

        def change():
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    RequirementService(db).update(
                        req["id"],
                        RequirementUpdate(revision=req["revision"], system_id=second),
                        uid,
                    )
                    return "ok"
                except AppError:
                    db.rollback()
                    return "blocked"

        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(attach), pool.submit(change)
            assert sorted([a.result(timeout=20), b.result(timeout=20)]) == ["blocked", "ok"]
        with Session(engine) as db:
            item = db.get(Requirement, req["id"])
            relation = db.scalar(
                select(VersionRequirement).where(
                    VersionRequirement.requirement_id == item.id,
                    VersionRequirement.active.is_(True),
                )
            )
            assert (relation is None and item.system_id == second) or (
                relation is not None and item.system_id == first
            )
        return
    if scenario == "migration":
        # Historical migration has no inferred ownership or modifications to existing columns.
        with Session(engine) as db:
            db.get(Version, ver["id"]).system_id = None
            db.commit()
        mysql = engine.dialect.name == "mysql"
        cfg = Config(
            str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
        )
        command.downgrade(cfg, "mysql57_0012" if mysql else "0014_issue4")
        with engine.connect() as conn:
            before = dict(conn.execute(text("SELECT * FROM rd_version")).mappings().one())
            req_before = dict(conn.execute(text("SELECT * FROM rd_requirement")).mappings().one())
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            after = dict(conn.execute(text("SELECT * FROM rd_version")).mappings().one())
            assert after.pop("system_id") is None and after == before
            assert (
                dict(conn.execute(text("SELECT * FROM rd_requirement")).mappings().one())
                == req_before
            )
        return
    bad = client.patch(
        f"/api/v1/requirements/{req['id']}",
        headers=headers,
        json={"revision": req["revision"], "system_id": second},
    )
    assert bad.status_code == 200, bad.text
    response = client.post(
        f"/api/v1/versions/{ver['id']}/requirements",
        headers=headers,
        json={
            "requirement_id": req["id"],
            "revision": bad.json()["revision"],
            "version_revision": ver["revision"],
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == 40975
    with Session(engine) as db:
        assert db.scalar(select(VersionRequirement)) is None
        assert db.get(Version, ver["id"]).revision == ver["revision"]

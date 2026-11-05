import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import Permission, Role, User


@pytest.mark.parametrize("collision", [False, True])
def test_collaboration_existing_postgres_upgrade(monkeypatch, collision):
    url = os.environ.get("ITERFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Real PostgreSQL required for migration acceptance")
    name = "collaboration_upgrade_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{name}"'))
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={name}")
    get_settings.cache_clear()
    engine = create_engine(url)
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    try:
        command.upgrade(cfg, "0004_integrity")
        digest = hash_password("ceshi123")
        with Session(engine) as db:
            user = User(
                username="ceshi001",
                display_name="原有账号",
                password_hash=digest,
                must_change_password=False,
            )
            db.add(user)
            db.add_all(
                Permission(code=c, name=c) for c in ["rd.requirement.view", "rd.requirement.status"]
            )
            db.flush()
            rid = db.scalar(
                text(
                    "INSERT INTO rd_requirement "
                    "(requirement_no,title,requirement_type,description,owner_id,"
                    "created_by,updated_by,status,source,priority,revision,create"
                    "d_at,updated_at) "
                    "VALUES "
                    "('REQ-LEGACY','原有中文需求','FEATURE','保留原数据',:uid,:uid,:uid,'DRA"
                    "FT','DIRECT','P2',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) "
                    "RETURNING id"
                ),
                {"uid": user.id},
            )
            if collision:
                db.add(
                    Role(
                        code="DEVELOPER",
                        name="既有自定义角色",
                        data_scope="SELF",
                        is_system=False,
                        enabled=False,
                    )
                )
            db.commit()
            uid = user.id
        if collision:
            with pytest.raises(RuntimeError, match="role code already exists"):
                command.upgrade(cfg, "head")
            assert "rd_requirement_participant" not in inspect(engine).get_table_names()
            with engine.connect() as db:
                assert (
                    db.scalar(text("SELECT version_num FROM alembic_version")) == "0004_integrity"
                )
            with Session(engine) as db:
                role = db.scalar(select(Role).where(Role.code == "DEVELOPER"))
                assert role.name == "既有自定义角色" and not role.enabled and not role.is_system
        else:
            command.upgrade(cfg, "0006_requirement_design_stage")
            with engine.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO rd_requirement_participant "
                        "(requirement_id,user_id,discipline) "
                        "VALUES (:rid,:uid,'DEVELOPMENT')"
                    ),
                    {"rid": rid, "uid": uid},
                )
            command.upgrade(cfg, "head")
            with engine.connect() as db:
                row = db.execute(
                    text(
                        "SELECT user_id,discipline,completed_at FROM rd_requirement_participant "
                        "WHERE requirement_id=:rid"
                    ),
                    {"rid": rid},
                ).one()
                assert row == (uid, "DEVELOPMENT", None), (
                    "Upgrade must not auto-confirm existing developers"
                )
            command.check(cfg)
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == ("0014_issue4")
            with Session(engine) as db:
                assert set(db.scalars(select(Role.code))) == {"DEVELOPER", "DESIGNER"}
        with Session(engine) as db:
            user = db.get(User, uid)
            assert user.password_hash == digest and not user.must_change_password
            req = db.execute(
                text(
                    "SELECT title, owner_id, revision, status, current_version_id FROM "
                    "rd_requirement WHERE id=:rid"
                ),
                {"rid": rid},
            ).one()
            assert req.title == "原有中文需求" and req.owner_id == uid and req.revision == 1
            assert req.status == "DRAFT" and req.current_version_id is None
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()

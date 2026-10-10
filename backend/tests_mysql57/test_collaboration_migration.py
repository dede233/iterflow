import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_acceptance import BACKEND, TEST_PORT

from alembic import command
from app.core import database
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.entities import Permission, Requirement, Role, User


@pytest.mark.parametrize("collision", [False, True])
def test_mysql_existing_upgrade_preserves_accounts_and_checks_role_collision(
    monkeypatch, collision
):
    url = make_url(os.environ["DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == TEST_PORT
    admin = create_engine(url)
    name = "iterflow_mysql57_upgrade_" + uuid4().hex
    with admin.connect() as db:
        db.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"))
    scoped = url.set(database=name)
    engine = create_engine(scoped)
    event.listen(engine, "connect", database.configure_mysql)
    monkeypatch.setenv("DATABASE_URL", scoped.render_as_string(hide_password=False))
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic-mysql.ini"))
    try:
        command.upgrade(cfg, "mysql57_0002")
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
            req = Requirement(
                requirement_no="REQ-LEGACY",
                title="原有中文需求",
                requirement_type="FEATURE",
                description="保留原数据",
                owner_id=user.id,
                created_by=user.id,
            )
            db.add(req)
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
            uid, rid = user.id, req.id
        if collision:
            with pytest.raises(RuntimeError, match="role code already exists"):
                command.upgrade(cfg, "head")
            assert "rd_requirement_participant" not in inspect(engine).get_table_names()
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == "mysql57_0002"
            with Session(engine) as db:
                role = db.scalar(select(Role).where(Role.code == "DEVELOPER"))
                assert role.name == "既有自定义角色" and not role.enabled and not role.is_system
        else:
            command.upgrade(cfg, "head")
            with engine.connect() as db:
                assert db.scalar(text("SELECT version_num FROM alembic_version")) == "mysql57_0003"
                assert (
                    db.scalar(
                        text(
                            "SELECT COUNT(*) FROM information_schema.triggers "
                            "WHERE trigger_schema=DATABASE()"
                        )
                    )
                    == 71
                )
            with Session(engine) as db:
                assert set(db.scalars(select(Role.code))) == {"DEVELOPER", "DESIGNER"}
        with Session(engine) as db:
            user = db.get(User, uid)
            assert user.password_hash == digest and not user.must_change_password
            req = db.get(Requirement, rid)
            assert req.title == "原有中文需求" and req.owner_id == uid and req.revision == 1
            assert req.status == "DRAFT" and req.current_version_id is None
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.connect() as db:
            db.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()

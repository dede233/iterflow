import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from test_acceptance import BACKEND, TEST_PORT
from version_role_migration_acceptance import exercise_upgrade

from app.core import database
from app.core.config import get_settings


@pytest.mark.parametrize("case", ["normal", "collision", "incomplete", "rollback"])
def test_version_permission_upgrade_mysql(monkeypatch, case):
    url = make_url(os.environ["DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == TEST_PORT
    admin = create_engine(url)
    name = "iterflow_mysql57_version_roles_" + uuid4().hex
    with admin.connect() as db:
        db.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"))
    scoped = url.set(database=name)
    engine = create_engine(scoped)
    event.listen(engine, "connect", database.configure_mysql)
    monkeypatch.setenv("DATABASE_URL", scoped.render_as_string(hide_password=False))
    get_settings.cache_clear()
    try:
        exercise_upgrade(engine, Config(str(BACKEND / "alembic-mysql.ini")), monkeypatch, case)
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.connect() as db:
            db.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()

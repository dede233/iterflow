import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from version_role_migration_acceptance import exercise_upgrade

from app.core.config import get_settings


@pytest.mark.parametrize("case", ["normal", "collision", "incomplete", "rollback"])
def test_version_permission_upgrade_postgres(monkeypatch, case):
    url = os.environ.get("ITERFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Real PostgreSQL required")
    schema = "version_roles_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    try:
        exercise_upgrade(
            engine, Config(str(Path(__file__).parents[1] / "alembic.ini")), monkeypatch, case
        )
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

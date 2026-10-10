import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from collaboration_acceptance import (
    RedactedHeaders,
    exercise_assignment_scope_and_notifications,
    exercise_concurrent_assignment,
    exercise_database_guards,
    exercise_design_blocks_publish,
    exercise_design_stage,
    exercise_invalid_and_rollback,
    exercise_publish_and_status_rollback,
    exercise_role_revocation,
    exercise_stage_rollback_and_race,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.cli.seed import seed_database
from app.core import database
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.models.entities import User


@pytest.fixture
def collaboration_pg(monkeypatch, tmp_path):
    url = os.environ.get("ITERFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Real PostgreSQL required for collaboration acceptance")
    schema = "collaboration_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, pool_size=8)
    try:
        command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
        with Session(engine) as db:
            seed_database(db, username="collaboration-admin", password="Fresh-admin-password!")
            user = db.scalar(select(User).where(User.username == "collaboration-admin"))
            user.must_change_password = False
            db.commit()
            uid = user.id
        monkeypatch.setattr(
            database, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False)
        )
        with TestClient(app) as client:
            yield (
                client,
                engine,
                uid,
                RedactedHeaders(Authorization="Bearer " + create_access_token(uid)),
            )
    finally:
        engine.dispose()
        get_settings.cache_clear()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_collaboration_scope_notifications_postgres(collaboration_pg):
    exercise_assignment_scope_and_notifications(collaboration_pg)


def test_collaboration_rollback_postgres(collaboration_pg, monkeypatch):
    exercise_invalid_and_rollback(collaboration_pg, monkeypatch)


def test_collaboration_concurrent_postgres(collaboration_pg):
    exercise_concurrent_assignment(collaboration_pg)


def test_collaboration_publish_and_status_rollback_postgres(collaboration_pg, monkeypatch):
    exercise_publish_and_status_rollback(collaboration_pg, monkeypatch)


def test_collaboration_revocation_postgres(collaboration_pg):
    exercise_role_revocation(collaboration_pg)


def test_collaboration_database_guards_postgres(collaboration_pg):
    exercise_database_guards(collaboration_pg)


def test_design_stage_flow(collaboration_pg):
    exercise_design_stage(collaboration_pg)


def test_design_stage_rollback_and_race(collaboration_pg, monkeypatch):
    exercise_stage_rollback_and_race(collaboration_pg, monkeypatch)


def test_design_stage_blocks_publish(collaboration_pg):
    exercise_design_blocks_publish(collaboration_pg)

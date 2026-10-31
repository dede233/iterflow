import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_integrity_migration_postgres import (
    _alembic_config,
    _seed_valid_relations,
    _upgrade_head,
    migration_schema,  # noqa: F401
)

from alembic import command


def test_workflow_migration_preserves_history_and_does_not_notify(migration_schema):  # noqa: F811
    engine, url, _schema = migration_schema
    _upgrade_head(url)
    with Session(engine) as db:
        ids = _seed_valid_relations(db)
    command.upgrade(_alembic_config(), "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM rd_requirement")).mappings().one()
        assert row["status"] == "CONFIRMED" and row["revision"] == 2
        assert row["owner_id"] == ids["user_id"]
        assert row["current_version_id"] == ids["version_a_id"]
        assert row["confirmed_revision"] == 1 and not row["legacy_completed"]
        event = conn.execute(text("SELECT * FROM rd_requirement_step")).mappings().one()
        assert event["action"] == "LEGACY_MIGRATION" and event["actor_id"] is None
        assert event["detail"]["original_status"] == "PLANNED"
        assert conn.scalar(text("SELECT count(*) FROM rd_requirement_participant")) == 0
        assert conn.scalar(text("SELECT count(*) FROM sys_collaboration_event")) == 0
    command.upgrade(_alembic_config(), "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM rd_requirement_step")) == 1
    with pytest.raises(RuntimeError, match="reviewed recovery"):
        command.downgrade(_alembic_config(), "0005_collaboration_people")

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


@pytest.mark.parametrize("old_status", ["PLANNED", "DONE", "ONLINE", "PAUSED", "DRAFT"])
def test_workflow_migration_preserves_history_and_does_not_notify(migration_schema, old_status):  # noqa: F811
    engine, url, _schema = migration_schema
    _upgrade_head(url)
    with Session(engine) as db:
        ids = _seed_valid_relations(db)
        db.execute(text("UPDATE rd_requirement SET status=:status"), {"status": old_status})
        db.commit()
    command.upgrade(_alembic_config(), "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM rd_requirement")).mappings().one()
        assert row["status"] == ("CONFIRMED" if old_status == "PLANNED" else old_status)
        assert row["revision"] == (2 if old_status == "PLANNED" else 1)
        assert row["owner_id"] == ids["user_id"]
        assert row["current_version_id"] == ids["version_a_id"]
        assert row["confirmed_revision"] == (None if old_status == "DRAFT" else 1)
        assert row["legacy_completed"] == (old_status in {"DONE", "ONLINE"})
        event = conn.execute(text("SELECT * FROM rd_requirement_step")).mappings().one()
        assert event["action"] == "LEGACY_MIGRATION" and event["actor_id"] is None
        assert event["detail"]["original_status"] == old_status
        assert conn.scalar(text("SELECT count(*) FROM rd_requirement_participant")) == 0
        assert conn.scalar(text("SELECT count(*) FROM sys_collaboration_event")) == 0
    command.upgrade(_alembic_config(), "head")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM rd_requirement_step")) == 1
    with pytest.raises(RuntimeError, match="reviewed recovery"):
        command.downgrade(_alembic_config(), "0005_collaboration_people")

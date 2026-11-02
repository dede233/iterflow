"""Exercise old-data preservation and safe downgrade on a disposable database."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command


def exercise_migration(engine, req_id, extra_user):
    mysql = engine.dialect.name == "mysql"
    config = Config(
        str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
    )
    previous = "mysql57_0009" if mysql else "0011_notification_delivery"
    current = "mysql57_0010" if mysql else "0012_multiple_acceptance"

    def rows():
        with engine.connect() as db:
            return db.execute(
                text(
                    "SELECT requirement_id,user_id,role,active FROM rd_requirement_actor "
                    "ORDER BY requirement_id,user_id,role"
                )
            ).all()

    before = rows()
    command.downgrade(config, previous)
    assert rows() == before
    if mysql:
        from unittest.mock import patch

        from app.cli import migrate
        from app.core.mysql_preflight import validate_mysql

        with engine.connect() as db:
            validate_mysql(db, allow_legacy=True)
            with pytest.raises(RuntimeError, match="Alembic head"):
                validate_mysql(db)
        # Exercise the deployment entry point, including its post-upgrade preflight.
        with patch.object(migrate, "engine", engine):
            migrate.main()
            migrate.main()  # A completed deployment must also be safe to rerun.
        with engine.connect() as db:
            validate_mysql(db)
    else:
        command.upgrade(config, "head")
    # Exercise this historical revision's guard in isolation. MySQL DDL cannot
    # roll back a later, successful downgrade when an earlier revision refuses.
    command.downgrade(config, current)
    assert rows() == before
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO rd_requirement_actor (requirement_id,user_id,role,active) "
                "VALUES (:rid,:uid,'ACCEPT',true)"
            ),
            {"rid": req_id, "uid": extra_user},
        )
    # The database still protects the single confirmer even if schema validation is bypassed.
    with pytest.raises(IntegrityError), engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO rd_requirement_actor (requirement_id,user_id,role,active) "
                "VALUES (:rid,:uid,'CONFIRM',true)"
            ),
            {"rid": req_id, "uid": extra_user},
        )
    multiple = rows()
    with pytest.raises(RuntimeError, match="refuse lossy downgrade"):
        command.downgrade(config, previous)
    assert rows() == multiple
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == current
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE rd_requirement_actor SET active=false WHERE requirement_id=:rid "
                "AND user_id=:uid AND role='ACCEPT'"
            ),
            {"rid": req_id, "uid": extra_user},
        )
    inactive = rows()
    command.downgrade(config, previous)
    command.upgrade(config, "head")
    assert rows() == inactive

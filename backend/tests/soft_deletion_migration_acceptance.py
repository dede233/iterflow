from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command


def exercise_soft_deletion_migration(api):
    _, engine, user_id, _ = api
    mysql = engine.dialect.name == "mysql"
    previous = "mysql57_0028" if mysql else "0030_ad_production_cc"
    ini = "alembic-mysql.ini" if mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / ini))
    command.downgrade(config, previous)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO ops_ad_production (id,work_date,content,issuer,kind,status,created_by,"
                "created_at,updated_at,revision) VALUES (111,'2026-11-27','original','publisher',"
                "'MERCHANT_AD','IN_PROGRESS',:uid,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,2)"
            ),
            {"uid": user_id},
        )
    command.upgrade(config, "head")
    for table in ("rd_version", "ops_ad_production"):
        columns = {col["name"]: col for col in inspect(engine).get_columns(table)}
        assert all(columns[k]["nullable"] for k in ("deleted_at", "deleted_by", "delete_reason"))
    with engine.begin() as db:
        assert db.execute(
            text("SELECT content,revision,deleted_at FROM ops_ad_production WHERE id=111")
        ).one() == ("original", 2, None)
        db.execute(text("UPDATE ops_ad_production SET status='WITHDRAWN' WHERE id=111"))
    with pytest.raises(RuntimeError, match="downgrade refused"):
        command.downgrade(config, previous)
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE ops_ad_production SET status='NOT_STARTED',deleted_at=CURRENT_TIMESTAMP,"
                "deleted_by=:uid,delete_reason='mistake' WHERE id=111"
            ),
            {"uid": user_id},
        )
    with pytest.raises(RuntimeError, match="downgrade refused"):
        command.downgrade(config, previous)
    with engine.connect() as db:
        assert db.execute(
            text("SELECT content,revision,delete_reason FROM ops_ad_production WHERE id=111")
        ).one() == ("original", 2, "mistake")

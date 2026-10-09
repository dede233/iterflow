"""Select the independent migration lineage from the configured dialect."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.core.database import engine
from app.core.mysql_preflight import validate_mysql


def main():
    root = Path(__file__).resolve().parents[2]
    mysql = engine.dialect.name == "mysql"
    if mysql:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            validate_mysql(connection, empty=not tables)
    config = Config(str(root / ("alembic-mysql.ini" if mysql else "alembic.ini")))
    command.upgrade(config, "head")
    if mysql:
        with engine.connect() as connection:
            validate_mysql(connection)


if __name__ == "__main__":
    main()

"""Exercise the shipped least-privilege template against the migrated schema."""

import re
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from test_acceptance import mysql_api as mysql_api

from app.core.database import configure_mysql
from app.core.mysql_preflight import validate_mysql


def test_runtime_template_covers_announcement_migration(mysql_api):
    _, admin, _, _ = mysql_api
    name = "grant_test_" + uuid4().hex[:16]
    password = token_urlsafe(32)
    template = (
        Path(__file__).resolve().parents[2] / "deploy/mysql57/runtime-grants.sql"
    ).read_text()
    statements = re.findall(r"^GRANT[^;]+;", template, re.MULTILINE)
    statements = [
        s.replace("`iterflow`", f"`{admin.url.database}`").replace(
            "'iterflow_runtime'@'APP_HOST'", f"'{name}'@'%'"
        )
        for s in statements
    ]
    runtime = create_engine(admin.url.set(username=name, password=password), hide_parameters=True)
    event.listen(runtime, "connect", configure_mysql)
    with admin.connect() as connection:
        connection.execute(
            text(f"CREATE USER '{name}'@'%' IDENTIFIED BY :password"), {"password": password}
        )
    try:
        old = [s for s in statements if "`sys_announcement" not in s]
        added = [s for s in statements if "`sys_announcement" in s]
        assert len(added) == 2
        with admin.connect() as connection:
            for statement in old:
                connection.execute(text(statement))
        with runtime.connect() as connection:
            with pytest.raises(RuntimeError, match="schema table set"):
                validate_mysql(connection, inspect_triggers=False)
        with admin.connect() as connection:
            for statement in added:
                connection.execute(text(statement))
        runtime.dispose()
        with runtime.connect() as connection:
            validate_mysql(connection, inspect_triggers=False)
            for table in ("sys_announcement", "sys_announcement_read"):
                privileges = set(
                    connection.scalars(
                        text(
                            "SELECT PRIVILEGE_TYPE FROM information_schema.TABLE_PRIVILEGES "
                            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
                        ),
                        {"table": table},
                    )
                )
                assert privileges == {"SELECT", "INSERT", "UPDATE", "DELETE"}
            assert not list(
                connection.execute(
                    text(
                        "SELECT * FROM information_schema.SCHEMA_PRIVILEGES "
                        "WHERE TABLE_SCHEMA = DATABASE()"
                    )
                )
            )
    finally:
        runtime.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP USER '{name}'@'%'"))

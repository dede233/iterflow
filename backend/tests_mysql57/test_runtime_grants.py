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


@pytest.mark.parametrize(
    "new_tables",
    [
        ("sys_announcement", "sys_announcement_read"),
        ("sys_release_target", "rd_release_batch", "rd_release_batch_target"),
    ],
)
def test_runtime_template_covers_new_tables(mysql_api, new_tables):
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
        old = [s for s in statements if not any(f"`{table}`" in s for table in new_tables)]
        added = [s for s in statements if any(f"`{table}`" in s for table in new_tables)]
        assert len(added) == len(new_tables)
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
            for table in new_tables:
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

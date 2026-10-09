"""Read-only deployment checks; never proves an untested server compatible."""

from sqlalchemy import inspect, text


def validate_mysql(connection, *, empty=False, inspect_triggers=True):
    row = connection.execute(
        text(
            "SELECT VERSION(), @@version_comment, @@character_set_database, @@collation_database,"
            " @@default_storage_engine, @@foreign_key_checks, @@unique_checks, @@innodb_strict_mode"
        )
    ).one()
    version, vendor, charset, collation, storage, fk, unique, strict = row
    if not version.startswith("5.7.") or "MariaDB" in vendor or "MariaDB" in version:
        raise RuntimeError("This path requires Oracle MySQL 5.7; vendor/version must be verified")
    if (charset, collation, storage.upper(), fk, unique, strict) != (
        "utf8mb4",
        "utf8mb4_bin",
        "INNODB",
        1,
        1,
        1,
    ):
        raise RuntimeError(
            "Required: utf8mb4/utf8mb4_bin, InnoDB; "
            "foreign_key_checks, unique_checks and innodb_strict_mode enabled"
        )
    tables = set(inspect(connection).get_table_names())
    if empty:
        if tables or inspect(connection).get_view_names():
            raise RuntimeError("New installation requires an entirely empty database")
    else:
        from app.core.database import Base
        from app.models import entities  # noqa: F401

        if tables != set(Base.metadata.tables) | {"alembic_version"}:
            raise RuntimeError("Initialized schema table set differs from the MySQL baseline")
        if connection.scalar(text("SELECT version_num FROM alembic_version")) != "mysql57_0001":
            raise RuntimeError("MySQL Alembic head is missing or unsupported")
        if inspect_triggers:
            triggers = set(
                connection.scalars(
                    text(
                        "SELECT trigger_name FROM information_schema.triggers "
                        "WHERE trigger_schema=DATABASE()"
                    )
                )
            )
            expected = {
                f"domain_{table}_{event}"
                for table in Base.metadata.tables
                for event in ("insert", "update", "delete")
            }
            if not expected <= triggers:
                raise RuntimeError("Required database integrity/domain triggers are missing")
        for table, index in [
            ("rd_requirement_feedback", "uq_feedback_primary_relation"),
            ("rd_version_requirement", "uq_requirement_active_version"),
        ]:
            found = [i for i in inspect(connection).get_indexes(table) if i["name"] == index]
            if len(found) != 1 or not found[0]["unique"]:
                raise RuntimeError("Required relationship unique index is missing")
    return {
        "version": version,
        "vendor": vendor,
        "table_count": len(tables),
        "scope": "read-only local/pre-deploy checks; full acceptance required separately",
    }

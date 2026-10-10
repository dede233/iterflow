"""Read-only deployment checks; never proves an untested server compatible."""

from sqlalchemy import inspect, text


def validate_mysql(
    connection,
    *,
    empty=False,
    inspect_triggers=True,
    allow_legacy=False,
    allow_empty_version_table=False,
):
    row = connection.execute(
        text(
            "SELECT VERSION(), @@version_comment, @@character_set_database, @@collation_database,"
            " @@default_storage_engine, @@foreign_key_checks, @@unique_checks,"
            " @@innodb_strict_mode,"
            " @@innodb_large_prefix, @@innodb_file_format, @@sql_mode, @@time_zone,"
            " @@log_bin, @@log_bin_trust_function_creators"
        )
    ).one()
    (
        version,
        vendor,
        charset,
        collation,
        storage,
        fk,
        unique,
        strict,
        large_prefix,
        file_format,
        sql_mode,
        time_zone,
        log_bin,
        trust_creators,
    ) = row
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
    required_modes = {
        "ONLY_FULL_GROUP_BY",
        "STRICT_ALL_TABLES",
        "NO_ZERO_DATE",
        "NO_ZERO_IN_DATE",
        "ERROR_FOR_DIVISION_BY_ZERO",
        "NO_ENGINE_SUBSTITUTION",
    }
    if not required_modes <= set(sql_mode.split(",")) or time_zone != "+00:00":
        raise RuntimeError(
            "Required: strict SQL modes and UTC in every application/migration session"
        )
    if file_format.lower() != "barracuda":
        raise RuntimeError("MySQL 5.7 requires Barracuda for explicit DYNAMIC row format")
    if (empty or allow_legacy) and log_bin and not trust_creators:
        raise RuntimeError("Binlogged MySQL must permit creation of integrity triggers/functions")
    tables = set(inspect(connection).get_table_names())
    if empty:
        if allow_empty_version_table and "alembic_version" in tables:
            if connection.scalar(text("SELECT COUNT(*) FROM alembic_version")) != 0:
                raise RuntimeError("New installation requires empty Alembic metadata")
            tables.remove("alembic_version")
        if tables or inspect(connection).get_view_names():
            raise RuntimeError("New installation requires an entirely empty database")
    else:
        from app.core.database import Base
        from app.models import entities  # noqa: F401

        head = connection.scalar(text("SELECT version_num FROM alembic_version"))
        legacy = head in {"mysql57_0001", "mysql57_0002"} and allow_legacy
        if head != "mysql57_0003" and not legacy:
            raise RuntimeError("MySQL Alembic head is missing or unsupported")
        portable = "iterflow_file_key_node" in tables
        business_tables = set(Base.metadata.tables)
        if legacy:
            business_tables.remove("rd_requirement_participant")
        expected_tables = business_tables | {"alembic_version"}
        if portable:
            expected_tables.add("iterflow_file_key_node")
        if tables != expected_tables:
            raise RuntimeError("Initialized schema table set differs from the MySQL baseline")
        if not portable and head != "mysql57_0001":
            raise RuntimeError("Exact file storage key registry is missing")
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
                for table in business_tables
                for event in ("insert", "update", "delete")
            }
            if portable:
                expected |= {
                    "domain_iterflow_file_key_node_" + event
                    for event in ("insert", "update", "delete")
                } | {"storage_key_sys_file_insert", "storage_key_sys_file_update"}
            if not expected <= triggers:
                raise RuntimeError("Required database integrity/domain triggers are missing")
            if (
                portable
                and connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM information_schema.routines "
                        "WHERE routine_schema=DATABASE() "
                        "AND routine_name='iterflow_register_file_key' AND routine_type='FUNCTION' "
                        "AND security_type='DEFINER' AND sql_data_access='MODIFIES SQL DATA'"
                    )
                )
                != 1
            ):
                raise RuntimeError("Required exact file storage key function is missing")
        if portable:
            file_columns = {c["name"]: c for c in inspect(connection).get_columns("sys_file")}
            if (
                getattr(file_columns["storage_key"]["type"], "length", None) != 2004
                or file_columns["storage_key_leaf_id"]["nullable"]
            ):
                raise RuntimeError("Exact file storage key overflow/leaf protection is missing")
            indexes = inspect(connection).get_indexes("sys_file")
            if not any(
                i["name"] == "uq_sys_file_storage_key_leaf"
                and i["unique"]
                and i["column_names"] == ["storage_key_leaf_id"]
                for i in indexes
            ):
                raise RuntimeError("Exact file storage key unique index is missing")
            if not any(
                i["name"] == "uq_file_key_edge"
                and i["unique"]
                and i["column_names"] == ["parent_id", "segment"]
                for i in inspect(connection).get_indexes("iterflow_file_key_node")
            ):
                raise RuntimeError("Exact file storage key edge index is missing")
            if (
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM iterflow_file_key_node WHERE id=1 AND parent_id=1 "
                        "AND OCTET_LENGTH(segment)=0"
                    )
                )
                != 1
            ):
                raise RuntimeError("Exact file storage key root is missing")
            if not any(
                fk["name"] == "fk_sys_file_storage_key_leaf"
                and fk["referred_table"] == "iterflow_file_key_node"
                and fk["constrained_columns"] == ["storage_key_leaf_id"]
                and fk["referred_columns"] == ["id"]
                for fk in inspect(connection).get_foreign_keys("sys_file")
            ):
                raise RuntimeError("Exact file storage key foreign key is missing")
            if not any(
                fk["name"] == "fk_file_key_parent"
                and fk["referred_table"] == "iterflow_file_key_node"
                and fk["constrained_columns"] == ["parent_id"]
                and fk["referred_columns"] == ["id"]
                for fk in inspect(connection).get_foreign_keys("iterflow_file_key_node")
            ):
                raise RuntimeError("Exact file storage key parent foreign key is missing")
        elif not any(
            i["unique"] and i["column_names"] == ["storage_key"]
            for i in inspect(connection).get_indexes("sys_file")
        ):
            raise RuntimeError("Legacy full file storage key unique index is missing")
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
        "large_prefix": bool(large_prefix),
        "session_innodb_strict_mode": bool(strict),
        "scope": "read-only local/pre-deploy checks; full acceptance required separately",
    }

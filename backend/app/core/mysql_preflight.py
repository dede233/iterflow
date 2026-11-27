"""Read-only deployment checks; never proves an untested server compatible."""

from sqlalchemy import BigInteger, inspect, text
from sqlalchemy.dialects.mysql import DATETIME, VARCHAR

CURRENT_MYSQL_HEAD = "mysql57_0027"


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
        legacy = (
            head
            in {
                "mysql57_0001",
                "mysql57_0002",
                "mysql57_0003",
                "mysql57_0004",
                "mysql57_0005",
                "mysql57_0006",
            }
            and allow_legacy
        )
        if not (
            head == CURRENT_MYSQL_HEAD
            or legacy
            or (
                allow_legacy
                and head
                in {
                    "mysql57_0009",
                    "mysql57_0010",
                    "mysql57_0011",
                    "mysql57_0012",
                    "mysql57_0013",
                    "mysql57_0014",
                    "mysql57_0015",
                    "mysql57_0016",
                    "mysql57_0017",
                    "mysql57_0018",
                    "mysql57_0019",
                    "mysql57_0020",
                    "mysql57_0021",
                    "mysql57_0022",
                    "mysql57_0023",
                    "mysql57_0024",
                    "mysql57_0025",
                    "mysql57_0026",
                }
            )
        ):
            raise RuntimeError("MySQL Alembic head is missing or unsupported")
        ad_production_kind_heads = {"mysql57_0025", "mysql57_0026", CURRENT_MYSQL_HEAD}
        ad_production_publication_heads = {"mysql57_0023", "mysql57_0024"}
        ad_production_publication_heads |= ad_production_kind_heads
        ad_production_people_heads = {"mysql57_0021", "mysql57_0022"} | (
            ad_production_publication_heads
        )
        rich_text_heads = {"mysql57_0020"} | ad_production_people_heads
        ad_production_heads = {"mysql57_0019"} | rich_text_heads
        wecom_heads = {"mysql57_0018"} | ad_production_heads
        online_review_heads = {"mysql57_0017"} | wecom_heads
        target_release_heads = {"mysql57_0015", "mysql57_0016"} | online_review_heads
        issue4_heads = {"mysql57_0012", "mysql57_0013", "mysql57_0014"} | target_release_heads
        if head in issue4_heads | {"mysql57_0011"} and "notice_acknowledged_at" not in {
            c["name"] for c in inspect(connection).get_columns("sys_mail_preference")
        }:
            raise RuntimeError("Mail notice acknowledgement column is missing")
        if head in issue4_heads:
            for table in ("rd_requirement", "rd_feedback"):
                columns = {c["name"] for c in inspect(connection).get_columns(table)}
                required = {"deleted_at", "deleted_by"}
                if table == "rd_requirement":
                    required.add("description_format")
                if not required <= columns:
                    raise RuntimeError("Issue 4 compatibility columns are missing")
            if "single_actor_role" in {
                c["name"] for c in inspect(connection).get_columns("rd_requirement_actor")
            }:
                raise RuntimeError("Multiple confirmer migration is incomplete")
        if head in issue4_heads - {"mysql57_0012"}:
            inspector = inspect(connection)
            if "system_id" not in {c["name"] for c in inspector.get_columns("rd_version")}:
                raise RuntimeError("Version system binding column is missing")
            if not any(
                fk["constrained_columns"] == ["system_id"]
                and fk["referred_table"] == "sys_business_system"
                for fk in inspector.get_foreign_keys("rd_version")
            ):
                raise RuntimeError("Version system binding foreign key is missing")
        portable = "iterflow_file_key_node" in tables
        business_tables = set(Base.metadata.tables)
        if head not in target_release_heads | {"mysql57_0014"}:
            business_tables -= {"sys_announcement", "sys_announcement_read"}
        if head not in target_release_heads:
            business_tables -= {"sys_release_target", "rd_release_batch", "rd_release_batch_target"}
        if head not in wecom_heads:
            business_tables.remove("sys_wecom_preference")
        if head not in ad_production_heads:
            business_tables.remove("ops_ad_production")
        if head not in online_review_heads:
            business_tables.remove("rd_requirement_online_feedback")
        if legacy:
            business_tables -= {
                "rd_feedback_recipient",
                "rd_requirement_actor",
                "sys_collaboration_event",
                "rd_requirement_step",
                "sys_mail_preference",
                "sys_notification_delivery",
            }
        if head in {"mysql57_0001", "mysql57_0002"}:
            business_tables.remove("rd_requirement_participant")
        expected_tables = business_tables | {"alembic_version"}
        if portable:
            expected_tables.add("iterflow_file_key_node")
        if tables != expected_tables:
            raise RuntimeError(
                "Initialized schema table set differs from the MySQL baseline; "
                "check migrations and runtime table grants"
            )
        if head in online_review_heads:
            table = "rd_requirement_online_feedback"
            inspector = inspect(connection)
            if inspector.get_pk_constraint(table)["constrained_columns"] != ["feedback_id"]:
                raise RuntimeError("Online feedback provenance primary key is missing")
            if not any(
                i["column_names"] == ["requirement_id"] for i in inspector.get_indexes(table)
            ):
                raise RuntimeError("Online feedback provenance requirement index is missing")
            references = {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys(table)
            }
            if references != {
                (("feedback_id",), "rd_feedback", ("id",)),
                (("requirement_id",), "rd_requirement", ("id",)),
            }:
                raise RuntimeError("Online feedback provenance foreign keys are missing")
        if head in wecom_heads:
            inspector = inspect(connection)
            if "queued_wecom_binding_id" not in {
                column["name"] for column in inspector.get_columns("sys_notification_delivery")
            }:
                raise RuntimeError("WeCom delivery binding snapshot column is missing")
            if not any(
                index["name"] == "uq_wecom_preference_member_key"
                and index["unique"]
                and index["column_names"] == ["corp_id", "member_key"]
                for index in inspector.get_indexes("sys_wecom_preference")
            ):
                raise RuntimeError("WeCom member binding uniqueness is missing")
        if head in ad_production_heads:
            inspector = inspect(connection)
            table = "ops_ad_production"
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            required = {
                "id",
                "work_date",
                "content",
                "issuer",
                "status",
                "created_at",
                "created_by",
                "updated_at",
                "revision",
            }
            if "updated_by" not in columns or any(
                column not in columns or columns[column]["nullable"] for column in required
            ):
                raise RuntimeError("Ad production record columns are missing or nullable")
            if inspector.get_pk_constraint(table)["constrained_columns"] != ["id"]:
                raise RuntimeError("Ad production primary key is missing")
            indexes = {tuple(index["column_names"]) for index in inspector.get_indexes(table)}
            if not {("work_date", "id"), ("created_by", "work_date", "id")} <= indexes:
                raise RuntimeError("Ad production listing indexes are missing")
            if head in ad_production_people_heads:
                people = {"receiver_id", "completed_by_id"}
                if any(
                    column not in columns
                    or not columns[column]["nullable"]
                    or not isinstance(columns[column]["type"], BigInteger)
                    for column in people
                ):
                    raise RuntimeError("Nullable ad production person IDs are missing or invalid")
                if not {("receiver_id", "work_date", "id"), ("completed_by_id",)} <= indexes:
                    raise RuntimeError("Ad production person indexes are missing")
                user_references = {
                    fk["constrained_columns"][0]
                    for fk in inspector.get_foreign_keys(table)
                    if len(fk["constrained_columns"]) == 1
                    and fk["referred_table"] == "sys_user"
                    and fk["referred_columns"] == ["id"]
                    and fk["options"].get("ondelete") in (None, "RESTRICT", "NO ACTION")
                }
                if not people <= user_references:
                    raise RuntimeError("Ad production person foreign keys are missing or invalid")
            if head in ad_production_publication_heads:
                title = columns.get("title")
                due_at = columns.get("due_at")
                if (
                    title is None
                    or not title["nullable"]
                    or not isinstance(title["type"], VARCHAR)
                    or title["type"].length != 200
                    or due_at is None
                    or not due_at["nullable"]
                    or not isinstance(due_at["type"], DATETIME)
                    or due_at["type"].fsp != 6
                ):
                    raise RuntimeError("Ad production publication columns are missing or invalid")
                if ("created_at", "id") not in indexes:
                    raise RuntimeError("Ad production publication listing index is missing")
        if head in ad_production_kind_heads:
            table = "ops_ad_production"
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            kind = columns.get("kind")
            result = columns.get("processing_result")
            if (
                kind is None
                or kind["nullable"]
                or not isinstance(kind["type"], VARCHAR)
                or kind["type"].length != 16
                or str(kind["default"]).strip("'\"") != "MATERIAL"
                or result is None
                or not result["nullable"]
            ):
                raise RuntimeError("Production request kind or processing result is invalid")
            indexes = {tuple(index["column_names"]) for index in inspector.get_indexes(table)}
            if ("kind", "created_at", "id") not in indexes:
                raise RuntimeError("Production request kind listing index is missing")
        if head in rich_text_heads:
            for table, field in (
                ("rd_feedback", "description_format"),
                ("ops_ad_production", "content_format"),
            ):
                if not any(
                    column["name"] == field and not column["nullable"]
                    for column in inspector.get_columns(table)
                ):
                    raise RuntimeError(f"Rich text format column is missing or nullable on {table}")
        if head in target_release_heads:
            if "release_frozen" not in {
                c["name"] for c in inspect(connection).get_columns("rd_version")
            }:
                raise RuntimeError("Release freeze column is missing")
            if not any(
                i["name"] == "uq_release_batch_initial"
                and i["unique"]
                and i["column_names"] == ["initial_version_id"]
                for i in inspect(connection).get_indexes("rd_release_batch")
            ):
                raise RuntimeError("Initial release uniqueness is missing")
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
            if head in issue4_heads | {
                "mysql57_0005",
                "mysql57_0006",
                "mysql57_0009",
                "mysql57_0010",
                "mysql57_0011",
            }:
                expected |= {
                    "completion_rd_requirement_participant_" + event
                    for event in ("insert", "update")
                }
                if "completed_at" not in {
                    c["name"] for c in inspect(connection).get_columns("rd_requirement_participant")
                }:
                    raise RuntimeError("Developer completion timestamp is missing")
            if head in target_release_heads:
                expected |= {
                    "immutable_release_target_update",
                    "immutable_release_target_delete",
                    "frozen_release_version_insert",
                    "frozen_release_version_update",
                }
            if not expected <= triggers:
                raise RuntimeError("Required database integrity/domain triggers are missing")
            if head in ad_production_kind_heads:
                rules = connection.scalars(
                    text(
                        "SELECT action_statement FROM information_schema.triggers "
                        "WHERE trigger_schema=DATABASE() AND trigger_name IN "
                        "('domain_ops_ad_production_insert','domain_ops_ad_production_update')"
                    )
                ).all()
                if len(rules) != 2 or any(
                    "NEW.kind" not in rule or "NEW.processing_result" not in rule for rule in rules
                ):
                    raise RuntimeError(
                        "Production request kind and result domain rules are missing"
                    )
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

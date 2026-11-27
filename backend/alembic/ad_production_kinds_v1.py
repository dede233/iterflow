"""Add merchant advertising to the existing ad production workflow."""

import sqlalchemy as sa

TABLE = "ops_ad_production"
KIND_INDEX = "ix_ad_production_kind_created_at_id"
KIND_CHECK = "ad_production_kind"
WORKFLOW_CHECK = "ck_ad_production_kind_workflow"
KINDS = ("MATERIAL", "MERCHANT_AD")
STATUSES = ("NOT_STARTED", "IN_PROGRESS", "SHIPPING", "COMPLETED")


def _allowed(values):
    return ", ".join(f"'{value}'" for value in values)


def _workflow(prefix=""):
    kind = f"{prefix}kind"
    status = f"{prefix}status"
    result = f"{prefix}processing_result"
    completer = f"{prefix}completed_by_id"
    return (
        f"({kind} = 'MATERIAL' AND {result} IS NULL) OR "
        f"({kind} = 'MERCHANT_AD' AND ("
        f"({status} = 'COMPLETED' AND {completer} IS NOT NULL "
        f"AND {result} IS NOT NULL AND char_length({result}) BETWEEN 1 AND 4000) "
        f"OR ({status} IN ('NOT_STARTED', 'IN_PROGRESS') AND {result} IS NULL)))"
    )


def _replace_mysql_triggers(op, *, include_kind):
    for event in ("insert", "update"):
        trigger = f"domain_{TABLE}_{event}"
        kind_guard = (
            f"IF BINARY NEW.kind NOT IN ({_allowed(KINDS)}) OR NOT ({_workflow('NEW.')}) THEN "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid ops_ad_production kind workflow'; "
            "END IF; "
            if include_kind
            else ""
        )
        op.execute(f"DROP TRIGGER {trigger}")
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE {event.upper()} ON {TABLE} "
            "FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
            f"END IF; IF BINARY NEW.status NOT IN ({_allowed(STATUSES)}) THEN "
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid ops_ad_production.status'; "
            f"END IF; {kind_guard}END"
        )


def upgrade(op):
    if op.get_bind().dialect.name == "mysql":
        op.execute(
            f"ALTER TABLE {TABLE} ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'MATERIAL', "
            "ADD COLUMN processing_result TEXT NULL, "
            f"ADD INDEX {KIND_INDEX} (kind, created_at, id)"
        )
        _replace_mysql_triggers(op, include_kind=True)
        return

    op.add_column(
        TABLE, sa.Column("kind", sa.String(16), nullable=False, server_default="MATERIAL")
    )
    op.add_column(TABLE, sa.Column("processing_result", sa.Text(), nullable=True))
    op.create_check_constraint(KIND_CHECK, TABLE, f"kind IN ({_allowed(KINDS)})")
    op.create_check_constraint(WORKFLOW_CHECK, TABLE, _workflow())
    op.create_index(KIND_INDEX, TABLE, ["kind", "created_at", "id"])


def downgrade(op):
    connection = op.get_bind()
    is_mysql = connection.dialect.name == "mysql"
    if not is_mysql:
        op.execute(f"LOCK TABLE {TABLE} IN ACCESS EXCLUSIVE MODE")
    if connection.scalar(
        sa.text(
            f"SELECT 1 FROM {TABLE} "
            "WHERE kind <> 'MATERIAL' OR processing_result IS NOT NULL LIMIT 1"
        )
    ):
        raise RuntimeError("Merchant advertising design requests exist; downgrade refused")

    if is_mysql:
        _replace_mysql_triggers(op, include_kind=False)
        op.execute(
            f"ALTER TABLE {TABLE} DROP INDEX {KIND_INDEX}, "
            "DROP COLUMN processing_result, DROP COLUMN kind"
        )
    else:
        op.drop_index(KIND_INDEX, table_name=TABLE)
        op.drop_constraint(WORKFLOW_CHECK, TABLE, type_="check")
        op.drop_constraint(KIND_CHECK, TABLE, type_="check")
        op.drop_column(TABLE, "processing_result")
        op.drop_column(TABLE, "kind")

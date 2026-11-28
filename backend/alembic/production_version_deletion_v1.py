"""Keep removed records and allow publishers to withdraw in-flight production."""

import sqlalchemy as sa

TABLES = ("rd_version", "ops_ad_production")
OPS = "ops_ad_production"


def _replace_status_checks(op, *, withdrawn):
    states = ["NOT_STARTED", "IN_PROGRESS", "SHIPPING", "COMPLETED"]
    unfinished = ["NOT_STARTED", "IN_PROGRESS"]
    if withdrawn:
        states.append("WITHDRAWN")
        unfinished.append("WITHDRAWN")

    def choices(values):
        return ", ".join(f"'{value}'" for value in values)

    mysql = op.get_bind().dialect.name == "mysql"
    row = "NEW." if mysql else ""
    workflow = (
        f"({row}kind = 'MATERIAL' AND {row}processing_result IS NULL) OR "
        f"({row}kind = 'MERCHANT_AD' AND (({row}status = 'COMPLETED' "
        f"AND {row}completed_by_id IS NOT NULL AND {row}processing_result IS NOT NULL "
        f"AND char_length({row}processing_result) BETWEEN 1 AND 4000) OR "
        f"({row}status IN ({choices(unfinished)}) AND {row}processing_result IS NULL)))"
    )
    if mysql:
        for event in ("insert", "update"):
            name = f"domain_{OPS}_{event}"
            op.execute(f"DROP TRIGGER {name}")
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {event.upper()} ON {OPS} FOR EACH ROW BEGIN "
                "IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE "
                "'45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; END IF; "
                f"IF BINARY NEW.status NOT IN ({choices(states)}) THEN SIGNAL SQLSTATE '45000' "
                "SET MESSAGE_TEXT='invalid ops_ad_production.status'; END IF; "
                f"IF BINARY NEW.kind NOT IN ('MATERIAL','MERCHANT_AD') OR NOT ({workflow}) THEN "
                "SIGNAL SQLSTATE '45000' "
                "SET MESSAGE_TEXT='invalid ops_ad_production kind workflow'; "
                "END IF; END"
            )
        return
    for name, expression in (
        ("ad_production_status", f"status IN ({choices(states)})"),
        ("ck_ad_production_kind_workflow", workflow),
    ):
        op.drop_constraint(name, OPS, type_="check")
        op.create_check_constraint(name, OPS, expression)


def upgrade(op):
    for table in TABLES:
        fk = f"fk_{table}_deleted_by"
        if op.get_bind().dialect.name == "mysql":
            op.execute(
                f"ALTER TABLE {table} ADD COLUMN deleted_at DATETIME(6) NULL, "
                "ADD COLUMN deleted_by BIGINT NULL, ADD COLUMN delete_reason VARCHAR(500) NULL, "
                f"ADD CONSTRAINT {fk} FOREIGN KEY (deleted_by) REFERENCES sys_user(id)"
            )
        else:
            op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True)))
            op.add_column(table, sa.Column("deleted_by", sa.BigInteger()))
            op.add_column(table, sa.Column("delete_reason", sa.String(500)))
            op.create_foreign_key(fk, table, "sys_user", ["deleted_by"], ["id"])
    _replace_status_checks(op, withdrawn=True)


def downgrade(op):
    connection = op.get_bind()
    mysql = connection.dialect.name == "mysql"
    if not mysql:
        op.execute("LOCK TABLE rd_version, ops_ad_production IN ACCESS EXCLUSIVE MODE")
    for table in TABLES:
        protected = "deleted_at IS NOT NULL OR deleted_by IS NOT NULL OR delete_reason IS NOT NULL"
        if table == OPS:
            protected += " OR status = 'WITHDRAWN'"
        if connection.scalar(sa.text(f"SELECT 1 FROM {table} WHERE {protected} LIMIT 1")):
            raise RuntimeError("Soft-deleted or withdrawn records exist; downgrade refused")
    _replace_status_checks(op, withdrawn=False)
    for table in TABLES:
        fk = f"fk_{table}_deleted_by"
        if mysql:
            op.execute(
                f"ALTER TABLE {table} DROP FOREIGN KEY {fk}, DROP COLUMN deleted_at, "
                "DROP COLUMN deleted_by, DROP COLUMN delete_reason"
            )
        else:
            op.drop_constraint(fk, table, type_="foreignkey")
            for column in ("deleted_at", "deleted_by", "delete_reason"):
                op.drop_column(table, column)

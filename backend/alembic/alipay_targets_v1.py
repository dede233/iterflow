"""Frozen platform extension; never rewrite successful publication snapshots."""

import sqlalchemy as sa

TABLES = {
    "sys_release_target": "release_target_platform",
    "rd_release_batch_target": "release_batch_target_platform",
}


def replace_guards(op, *, is_mysql, alipay):
    platforms = "'PC_WEB','WECHAT_MINI_PROGRAM'"
    if alipay:
        platforms += ",'ALIPAY_MINI_PROGRAM'"
    for table, constraint in TABLES.items():
        if not is_mysql:
            op.drop_constraint(constraint, table, type_="check")
            op.create_check_constraint(constraint, table, f"platform IN ({platforms})")
            continue
        condition = f"NEW.platform NOT IN ({platforms})"
        if table == "sys_release_target":
            condition += " OR NEW.enabled NOT IN (0,1)"
        else:
            condition += (
                " OR NEW.active NOT IN (0,1)"
                " OR (NEW.completed_at IS NULL) <> (NEW.recorded_at IS NULL)"
                " OR (NEW.completed_at IS NULL) <> (NEW.completed_by IS NULL)"
            )
        for event in ("insert", "update"):
            name = f"domain_{table}_{event}"
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {event.upper()} ON {table} FOR EACH ROW BEGIN "
                "IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
                f"END IF; IF {condition} THEN SIGNAL SQLSTATE '45000' "
                "SET MESSAGE_TEXT='invalid target release domain'; END IF; END"
            )


def upgrade(op, *, is_mysql):
    replace_guards(op, is_mysql=is_mysql, alipay=True)


def downgrade(op, *, is_mysql):
    # Check both live directory and snapshots before any DDL (MySQL auto-commits).
    for table in TABLES:
        if op.get_bind().scalar(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE platform='ALIPAY_MINI_PROGRAM'")
        ):
            raise RuntimeError("Alipay target history exists; cannot downgrade platform support")
    replace_guards(op, is_mysql=is_mysql, alipay=False)

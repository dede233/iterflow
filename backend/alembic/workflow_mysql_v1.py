"""Frozen MySQL equivalents of the unpublished collaboration migrations."""

import runpy
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME


class MySQLOperations:
    def __init__(self, op):
        self.op = op

    def __getattr__(self, name):
        return getattr(self.op, name)

    @staticmethod
    def column(column):
        if isinstance(column, sa.Column) and isinstance(column.type, sa.DateTime):
            column.type = DATETIME(fsp=6)
        return column

    def create_table(self, name, *columns, **kwargs):
        return self.op.create_table(
            name,
            *(self.column(c) for c in columns),
            mysql_engine="InnoDB",
            mysql_row_format="DYNAMIC",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_bin",
            **kwargs,
        )

    def add_column(self, table, column, **kwargs):
        return self.op.add_column(table, self.column(column), **kwargs)

    def create_index(self, name, table, columns, **kwargs):
        if name == "uq_requirement_single_actor_role":
            self.op.add_column(
                table,
                sa.Column(
                    "single_actor_role",
                    sa.String(16),
                    sa.Computed(
                        "CASE WHEN active = 1 AND role IN ('CONFIRM', 'ACCEPT') THEN role ELSE NULL END",
                        persisted=True,
                    ),
                ),
            )
            return self.op.create_unique_constraint(
                name, table, ["requirement_id", "single_actor_role"]
            )
        return self.op.create_index(name, table, columns, **kwargs)


def upgrade_revision(revision, op):
    module = runpy.run_path(str(Path(__file__).parent / "versions" / (revision + ".py")))
    module["upgrade"].__globals__["op"] = MySQLOperations(op)
    module["upgrade"]()
    # MySQL 5.7 ignores CHECK; enforce data domains and integrity switch guards.
    if revision == "0009_collaboration_people":
        for table, clause in {
            "rd_feedback_recipient": "NEW.active NOT IN (0,1)",
            "rd_requirement_actor": "NEW.active NOT IN (0,1) OR BINARY NEW.role NOT IN ('CONFIRM','DESIGN','DEVELOP','ACCEPT') OR OCTET_LENGTH(NEW.role) NOT IN (6,7)",
            "sys_collaboration_event": None,
        }.items():
            for event in ("insert", "update", "delete"):
                guard = (
                    ""
                    if event == "delete" or not clause
                    else f"IF {clause} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid collaboration domain'; END IF;"
                )
                op.execute(
                    f"CREATE TRIGGER domain_{table}_{event} BEFORE {event.upper()} ON {table} FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; END IF; {guard} END"
                )

    for table in {
        "0010_requirement_workflow": ["rd_requirement_step"],
        "0011_notification_delivery": ["sys_mail_preference", "sys_notification_delivery"],
    }.get(revision, []):
        for event in ("insert", "update", "delete"):
            op.execute(
                f"CREATE TRIGGER domain_{table}_{event} BEFORE {event.upper()} ON {table} FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; END IF; END"
            )

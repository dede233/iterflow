"""Frozen schema for online feedback provenance."""

import sqlalchemy as sa

TABLE = "rd_requirement_online_feedback"
REQUIREMENT_INDEX = "ix_requirement_online_feedback_requirement_id"


def upgrade(op, *, is_mysql):
    options = (
        {
            "mysql_engine": "InnoDB",
            "mysql_row_format": "DYNAMIC",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_bin",
        }
        if is_mysql
        else {}
    )
    op.create_table(
        TABLE,
        sa.Column("feedback_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["rd_feedback.id"],
            name="fk_online_feedback_feedback",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["rd_requirement.id"],
            name="fk_online_feedback_requirement",
            ondelete="RESTRICT",
        ),
        **options,
    )
    op.create_index(REQUIREMENT_INDEX, TABLE, ["requirement_id"])
    if is_mysql:
        for event in ("insert", "update", "delete"):
            op.execute(
                f"CREATE TRIGGER domain_{TABLE}_{event} BEFORE {event.upper()} ON {TABLE} "
                "FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
                "END IF; END"
            )


def downgrade(op):
    if op.get_bind().scalar(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")):
        raise RuntimeError("Online feedback history exists; cannot downgrade provenance support")
    op.drop_table(TABLE)

"""Add record-level CC relationships for both production kinds."""

import sqlalchemy as sa

TABLE = "ops_ad_production_cc_user"


def upgrade(op):
    op.create_table(
        TABLE,
        sa.Column("ad_production_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("ad_production_id", "user_id"),
        sa.ForeignKeyConstraint(
            ["ad_production_id"],
            ["ops_ad_production.id"],
            name="fk_ad_production_cc_record",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["sys_user.id"], name="fk_ad_production_cc_user", ondelete="RESTRICT"
        ),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_ad_production_cc_user_id", TABLE, ["user_id"])
    if op.get_bind().dialect.name == "mysql":
        for event in ("insert", "update", "delete"):
            op.execute(
                f"CREATE TRIGGER domain_{TABLE}_{event} BEFORE {event.upper()} ON {TABLE} "
                "FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
                "END IF; END"
            )


def downgrade(op):
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(f"LOCK TABLE {TABLE} IN ACCESS EXCLUSIVE MODE")
    if connection.scalar(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")):
        raise RuntimeError("Ad production CC relationships exist; downgrade refused")
    op.drop_table(TABLE)

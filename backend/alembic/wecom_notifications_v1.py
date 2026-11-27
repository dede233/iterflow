"""Frozen schema for individual WeCom notifications."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

PREFERENCE_TABLE = "sys_wecom_preference"
DELIVERY_TABLE = "sys_notification_delivery"


def upgrade(op, *, is_mysql):
    user_id_type = (
        mysql.VARCHAR(64, charset="ascii", collation="ascii_bin") if is_mysql else sa.String(64)
    )
    corp_id_type = (
        mysql.VARCHAR(128, charset="utf8mb4", collation="utf8mb4_bin")
        if is_mysql
        else sa.String(128)
    )
    timestamp_type = mysql.DATETIME(fsp=6) if is_mysql else sa.DateTime(timezone=True)
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
        PREFERENCE_TABLE,
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("sys_user.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="OFF"),
        sa.Column("corp_id", corp_id_type),
        sa.Column("member_user_id", user_id_type),
        sa.Column("member_key", user_id_type),
        sa.Column("binding_id", sa.String(36)),
        sa.Column("eligible_since", timestamp_type),
        sa.UniqueConstraint("corp_id", "member_key", name="uq_wecom_preference_member_key"),
        **options,
    )
    op.add_column(DELIVERY_TABLE, sa.Column("queued_wecom_binding_id", sa.String(36)))
    if is_mysql:
        for event in ("insert", "update", "delete"):
            op.execute(
                f"CREATE TRIGGER domain_{PREFERENCE_TABLE}_{event} BEFORE {event.upper()} "
                f"ON {PREFERENCE_TABLE} FOR EACH ROW BEGIN "
                "IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
                "END IF; END"
            )


def downgrade(op):
    connection = op.get_bind()
    if connection.scalar(sa.text(f"SELECT 1 FROM {PREFERENCE_TABLE} LIMIT 1")) or connection.scalar(
        sa.text(f"SELECT 1 FROM {DELIVERY_TABLE} WHERE channel = 'WECOM' LIMIT 1")
    ):
        raise RuntimeError("WeCom settings or delivery history exist; downgrade refused")
    op.drop_column(DELIVERY_TABLE, "queued_wecom_binding_id")
    op.drop_table(PREFERENCE_TABLE)

"""Product announcements and account-wide reading history; no automatic publication."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "mysql57_0014"
down_revision = "mysql57_0013"
branch_labels = None
depends_on = None


def upgrade():
    timestamp = mysql.DATETIME(fsp=6)
    options = dict(
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_bin",
        mysql_row_format="DYNAMIC",
    )
    op.create_table(
        "sys_announcement",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version_label", sa.String(100), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("important", sa.Boolean(), nullable=False),
        sa.Column("published_at", timestamp, nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        **options,
    )
    op.create_index("ix_sys_announcement_published_at", "sys_announcement", ["published_at"])
    op.create_table(
        "sys_announcement_read",
        sa.Column(
            "announcement_id",
            sa.BigInteger(),
            sa.ForeignKey("sys_announcement.id"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("sys_user.id"), primary_key=True),
        sa.Column("read_at", timestamp, nullable=False),
        **options,
    )

    for table in ("sys_announcement", "sys_announcement_read"):
        for event in ("insert", "update", "delete"):
            domain = (
                "IF NEW.important NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid announcement domain'; END IF;"
                if table == "sys_announcement" and event != "delete"
                else ""
            )
            op.execute(
                f"CREATE TRIGGER domain_{table}_{event} BEFORE {event.upper()} ON {table} FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; END IF; {domain} END"
            )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM sys_announcement")):
        raise RuntimeError("Announcements exist; refuse lossy downgrade")
    op.drop_table("sys_announcement_read")
    op.drop_table("sys_announcement")

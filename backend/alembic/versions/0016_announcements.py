"""Product announcements and account-wide reading history; no automatic publication."""

import sqlalchemy as sa
from alembic import op

revision = "0016_announcements"
down_revision = "0015_system_binding"
branch_labels = None
depends_on = None


def upgrade():
    timestamp = sa.DateTime(timezone=True)
    options = {}
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


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM sys_announcement")):
        raise RuntimeError("Announcements exist; refuse lossy downgrade")
    op.drop_table("sys_announcement_read")
    op.drop_table("sys_announcement")

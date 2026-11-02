"""Persist account-wide acknowledgement of the mail setup notice."""

import sqlalchemy as sa

from alembic import op

revision = "0013_mail_notice"
down_revision = "0012_multiple_acceptance"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sys_mail_preference",
        sa.Column("notice_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM sys_mail_preference WHERE notice_acknowledged_at IS NOT NULL")
    ):
        raise RuntimeError("Mail notice acknowledgements exist; refuse lossy downgrade")
    op.drop_column("sys_mail_preference", "notice_acknowledged_at")

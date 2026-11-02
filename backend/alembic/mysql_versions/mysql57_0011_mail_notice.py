"""Persist account-wide acknowledgement of the mail setup notice."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "mysql57_0011"
down_revision = "mysql57_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sys_mail_preference",
        sa.Column("notice_acknowledged_at", mysql.DATETIME(fsp=6), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM sys_mail_preference WHERE notice_acknowledged_at IS NOT NULL")
    ):
        raise RuntimeError("Mail notice acknowledgements exist; refuse lossy downgrade")
    op.drop_column("sys_mail_preference", "notice_acknowledged_at")

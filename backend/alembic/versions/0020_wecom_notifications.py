"""Persist individual WeCom notification preferences and delivery identity."""

import runpy
from pathlib import Path

from alembic import op

revision = "0020_wecom_notifications"
down_revision = "0019_online_review"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "wecom_notifications_v1.py"))["upgrade"](
        op, is_mysql=False
    )


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "wecom_notifications_v1.py"))["downgrade"](op)

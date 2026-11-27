"""Add ad production records and their permission catalog."""

import runpy
from pathlib import Path

from alembic import op

revision = "0021_ad_production"
down_revision = "0020_wecom_notifications"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_v1.py"))["upgrade"](
        op, is_mysql=False
    )


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_v1.py"))["downgrade"](op)

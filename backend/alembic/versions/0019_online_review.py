"""Store the source of feedback submitted on published requirements."""

import runpy
from pathlib import Path

from alembic import op

revision = "0019_online_review"
down_revision = "0018_alipay_targets"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "online_review_v1.py"))["upgrade"](
        op, is_mysql=False
    )


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "online_review_v1.py"))["downgrade"](op)

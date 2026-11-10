"""Allow Alipay mini programs in directories and publication snapshots."""

import runpy
from pathlib import Path

from alembic import op

revision = "0018_alipay_targets"
down_revision = "0017_target_releases"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "alipay_targets_v1.py"))["upgrade"](
        op, is_mysql=False
    )


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "alipay_targets_v1.py"))["downgrade"](
        op, is_mysql=False
    )

"""Add ad production CC relationships."""

import runpy
from pathlib import Path

from alembic import op

revision = "0030_ad_production_cc"
down_revision = "0029_ops_role_defaults"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ad_production_cc_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

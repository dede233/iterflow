"""Add ad production CC relationships in MySQL."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0028"
down_revision = "mysql57_0027"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ad_production_cc_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

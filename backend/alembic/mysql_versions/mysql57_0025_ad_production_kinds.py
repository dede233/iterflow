"""Add merchant advertising to the shared MySQL production workflow."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0025"
down_revision = "mysql57_0024"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ad_production_kinds_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

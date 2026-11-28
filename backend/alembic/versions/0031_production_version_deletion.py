"""Add soft deletion and production withdrawal."""

import runpy
from pathlib import Path

from alembic import op

revision = "0031_production_version_deletion"
down_revision = "0030_ad_production_cc"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "production_version_deletion_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

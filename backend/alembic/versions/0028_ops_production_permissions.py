"""Separate the operations production permission catalogs."""

import runpy
from pathlib import Path

from alembic import op

revision = "0028_ops_production_permissions"
down_revision = "0027_ad_production_kinds"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ops_production_permissions_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op.get_bind())


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op.get_bind())

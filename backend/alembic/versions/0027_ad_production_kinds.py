"""Add merchant advertising to the shared production workflow."""

import runpy
from pathlib import Path

from alembic import op

revision = "0027_ad_production_kinds"
down_revision = "0026_material_production_names"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ad_production_kinds_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

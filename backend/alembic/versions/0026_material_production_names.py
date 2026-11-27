"""Rename the built-in material production display labels."""

import runpy
from pathlib import Path

from alembic import op

revision = "0026_material_production_names"
down_revision = "0025_ad_production_publication"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "material_production_names_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["rename"](op.get_bind())


def downgrade():
    runpy.run_path(str(_MIGRATION))["rename"](op.get_bind(), downgrade=True)

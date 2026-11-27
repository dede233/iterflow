"""Add ad production publication details."""

import runpy
from pathlib import Path

from alembic import op

revision = "0025_ad_production_publication"
down_revision = "0024_ad_production_roles"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ad_production_publication_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op)


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op)

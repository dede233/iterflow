"""Separate the operations production permission catalogs in MySQL."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0026"
down_revision = "mysql57_0025"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ops_production_permissions_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["upgrade"](op.get_bind())


def downgrade():
    runpy.run_path(str(_MIGRATION))["downgrade"](op.get_bind())

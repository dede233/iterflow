"""Grant operations production defaults to customer service and designers in MySQL."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0027"
down_revision = "mysql57_0026"
branch_labels = None
depends_on = None
_MIGRATION = Path(__file__).parents[1] / "ops_role_defaults_v1.py"


def upgrade():
    runpy.run_path(str(_MIGRATION))["change_grants"](op.get_bind())


def downgrade():
    runpy.run_path(str(_MIGRATION))["change_grants"](op.get_bind(), downgrade=True)

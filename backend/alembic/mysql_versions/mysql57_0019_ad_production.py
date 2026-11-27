"""Add ad production records and their permission catalog."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0019"
down_revision = "mysql57_0018"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_v1.py"))["upgrade"](
        op, is_mysql=True
    )


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_v1.py"))["downgrade"](op)

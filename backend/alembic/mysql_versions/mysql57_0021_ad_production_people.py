"""Persist assigned designers and completers for ad production on MySQL 5.7."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0021"
down_revision = "mysql57_0020"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_people_v1.py"))["upgrade"](op)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_people_v1.py"))["downgrade"](op)

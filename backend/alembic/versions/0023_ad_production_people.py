"""Persist assigned designers and completers for ad production."""

import runpy
from pathlib import Path

from alembic import op

revision = "0023_ad_production_people"
down_revision = "0022_feedback_ad_rich_text"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_people_v1.py"))["upgrade"](op)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_people_v1.py"))["downgrade"](op)

"""Persist rich text format for feedback and ad production."""

import runpy
from pathlib import Path

from alembic import op

revision = "0022_feedback_ad_rich_text"
down_revision = "0021_ad_production"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "feedback_ad_rich_text_v1.py"))["upgrade"](op)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "feedback_ad_rich_text_v1.py"))["downgrade"](op)

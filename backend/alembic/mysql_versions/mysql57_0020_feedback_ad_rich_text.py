"""Persist rich text format for feedback and ad production on MySQL 5.7."""

import runpy
from pathlib import Path

from alembic import op

revision = "mysql57_0020"
down_revision = "mysql57_0019"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "feedback_ad_rich_text_v1.py"))["upgrade"](op)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "feedback_ad_rich_text_v1.py"))["downgrade"](op)

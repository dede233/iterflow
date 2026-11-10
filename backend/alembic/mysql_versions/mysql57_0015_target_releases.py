"""Release targets, batches and per-target publication history."""
from alembic import op
import runpy
from pathlib import Path

revision = "mysql57_0015"
down_revision = "mysql57_0014"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "multi_target_release_v1.py"))["upgrade"](op, is_mysql=True)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "multi_target_release_v1.py"))["downgrade"](op, is_mysql=True)

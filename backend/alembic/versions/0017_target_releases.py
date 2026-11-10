"""Release targets, explicit batches and immutable actual-success records."""
from alembic import op
import runpy
from pathlib import Path

revision = "0017_target_releases"
down_revision = "0016_announcements"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "multi_target_release_v1.py"))["upgrade"](op, is_mysql=False)


def downgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "multi_target_release_v1.py"))["downgrade"](op, is_mysql=False)

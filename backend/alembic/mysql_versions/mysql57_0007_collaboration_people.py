"""Apply collaboration workflow to MySQL 5.7; stop writers before DDL."""

import runpy
from pathlib import Path
from alembic import op
from sqlalchemy import text

revision = "mysql57_0007"
down_revision = "mysql57_0006"
branch_labels = None
depends_on = None


def upgrade():
    helper = runpy.run_path(str(Path(__file__).parents[1] / "workflow_mysql_v1.py"))
    helper["upgrade_revision"]("0009_collaboration_people", op)


def downgrade():
    raise RuntimeError("Workflow history requires reviewed recovery; downgrade refused")

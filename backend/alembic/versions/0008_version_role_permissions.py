"""Grant the three approved base roles the complete version workflow."""

import runpy
from pathlib import Path

from alembic import op

revision = "0008_version_role_permissions"
down_revision = "0007_development_completion"
branch_labels = None
depends_on = None


def upgrade():
    helper = runpy.run_path(str(Path(__file__).parents[1] / "version_role_permissions_v1.py"))
    helper["upgrade_permissions"](op.get_bind())


def downgrade():
    raise RuntimeError("Permission grants may predate migration; automatic revocation refused")

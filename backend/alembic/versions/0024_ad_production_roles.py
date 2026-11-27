"""Name the built-in ad production publisher and add the completer role."""

import runpy
from pathlib import Path

from alembic import op

revision = "0024_ad_production_roles"
down_revision = "0023_ad_production_people"
branch_labels = None
depends_on = None


def upgrade():
    runpy.run_path(str(Path(__file__).parents[1] / "ad_production_roles_v1.py"))["upgrade"](
        op.get_bind()
    )


def downgrade():
    """Preserve role identities, assignments, permissions, and audit history."""

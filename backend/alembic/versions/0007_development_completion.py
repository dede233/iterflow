"""Require each developer's own completion acknowledgement before publish."""

import sqlalchemy as sa

from alembic import op

revision = "0007_development_completion"
down_revision = "0006_requirement_design_stage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rd_requirement_participant",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "participant_completion",
        "rd_requirement_participant",
        "completed_at IS NULL OR discipline = 'DEVELOPMENT'",
    )


def downgrade():
    raise RuntimeError(
        "Developer confirmations are business history; destructive downgrade refused"
    )

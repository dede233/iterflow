"""Add multi-person requirement collaboration without rewriting released history."""

import runpy
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0005_requirement_collaboration"
down_revision = "0004_integrity"
branch_labels = None
depends_on = None


def upgrade():
    helpers = runpy.run_path(str(Path(__file__).parents[1] / "requirement_collaboration_v1.py"))
    helpers["validate_role_codes"](op.get_bind())
    op.create_table(
        "rd_requirement_participant",
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("discipline", sa.String(11), nullable=False),
        sa.PrimaryKeyConstraint("requirement_id", "user_id", "discipline"),
        sa.ForeignKeyConstraint(["requirement_id"], ["rd_requirement.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "discipline IN ('DEVELOPMENT', 'DESIGN')", name="participant_discipline"
        ),
    )
    op.create_index("ix_requirement_participant_user", "rd_requirement_participant", ["user_id"])
    runpy.run_path(str(Path(__file__).parents[1] / "requirement_collaboration_v1.py"))["add_roles"](
        op.get_bind()
    )


def downgrade():
    raise RuntimeError("Collaboration contains business assignments; destructive downgrade refused")

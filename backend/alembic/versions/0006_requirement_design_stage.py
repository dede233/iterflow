"""User-approved optional design stage; preserve prior state values and history."""

from alembic import op

revision = "0006_requirement_design_stage"
down_revision = "0005_requirement_collaboration"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("requirement_status", "rd_requirement", type_="check")
    op.create_check_constraint(
        "requirement_status",
        "rd_requirement",
        "status IN ('DRAFT','CONFIRMED','PLANNED','DESIGNING','DEVELOPING',"
        "'TESTING','DONE','ONLINE','PAUSED','CANCELED')",
    )


def downgrade():
    raise RuntimeError("Design state is business history; destructive downgrade refused")

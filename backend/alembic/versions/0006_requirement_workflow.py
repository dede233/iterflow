"""Simplify requirement workflow while preserving historical completion."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0006_requirement_workflow"
down_revision = "0005_collaboration_people"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rd_requirement", sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("rd_requirement", sa.Column("confirmed_revision", sa.Integer()))
    op.add_column("rd_requirement", sa.Column("legacy_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("rd_requirement", sa.Column("design_status", sa.String(20), nullable=False, server_default="NOT_REQUIRED"))
    op.add_column("rd_requirement", sa.Column("paused_from", sa.String(20)))
    op.create_table("rd_requirement_step",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("requirement_id", sa.BigInteger(), sa.ForeignKey("rd_requirement.id"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False))
    op.create_index("ix_rd_requirement_step_requirement_id", "rd_requirement_step", ["requirement_id"])
    conn = op.get_bind()
    for row in conn.execute(sa.text("SELECT id, status FROM rd_requirement")):
        conn.execute(sa.text("INSERT INTO rd_requirement_step (id, requirement_id, action, actor_id, created_at, detail) VALUES (:id, :rid, 'LEGACY_MIGRATION', NULL, CURRENT_TIMESTAMP, CAST(:detail AS json))"),
                     {"id":str(uuid4()), "rid":row.id, "detail":'{"original_status":"'+row.status+'"}'})
    conn.execute(sa.text("UPDATE rd_requirement SET confirmed_revision=1 WHERE status NOT IN ('DRAFT', 'CANCELED')"))
    conn.execute(sa.text("UPDATE rd_requirement SET legacy_completed=true WHERE status IN ('DONE', 'ONLINE')"))
    conn.execute(sa.text("UPDATE rd_requirement SET status='CONFIRMED', revision=revision+1 WHERE status='PLANNED'"))


def downgrade():
    raise RuntimeError("Workflow history requires a reviewed recovery; automatic downgrade is disabled")

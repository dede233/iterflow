"""Add collaboration people and transactional events without inferring historical actions."""

from alembic import op
import sqlalchemy as sa

revision = "0005_collaboration_people"
down_revision = "0004_integrity"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("handler_id", "accepted_by"):
        op.add_column("rd_feedback", sa.Column(name, sa.BigInteger(), nullable=True))
        op.create_foreign_key(f"fk_feedback_{name}", "rd_feedback", "sys_user", [name], ["id"])
    op.add_column("rd_feedback", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.create_table(
        "rd_feedback_recipient",
        sa.Column(
            "feedback_id", sa.BigInteger(), sa.ForeignKey("rd_feedback.id"), primary_key=True
        ),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("sys_user.id"), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "rd_requirement_participant",
        sa.Column(
            "requirement_id", sa.BigInteger(), sa.ForeignKey("rd_requirement.id"), primary_key=True
        ),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("sys_user.id"), primary_key=True),
        sa.Column("role", sa.String(16), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "sys_collaboration_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    connection = op.get_bind()
    for table in ("sys_collaboration_event", "rd_requirement_participant", "rd_feedback_recipient"):
        if connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")):
            raise RuntimeError("Collaboration data exists; refuse destructive downgrade")
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM rd_feedback WHERE accepted_by IS NOT NULL OR handler_id IS NOT NULL OR accepted_at IS NOT NULL)")):
        raise RuntimeError("Feedback acceptance history exists; refuse destructive downgrade")
    for table in ("sys_collaboration_event", "rd_requirement_participant", "rd_feedback_recipient"):
        op.drop_table(table)
    op.drop_column("rd_feedback", "accepted_at")
    for name in ("accepted_by", "handler_id"):
        op.drop_constraint(f"fk_feedback_{name}", "rd_feedback", type_="foreignkey")
        op.drop_column("rd_feedback", name)

"""Allow multiple acceptance people while retaining the single confirmer constraint."""

import sqlalchemy as sa

from alembic import op

revision = "0012_multiple_acceptance"
down_revision = "0011_notification_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_requirement_single_actor_role", table_name="rd_requirement_actor")
    op.create_index(
        "uq_requirement_single_actor_role",
        "rd_requirement_actor",
        ["requirement_id", "role"],
        unique=True,
        postgresql_where=sa.text("active AND role = 'CONFIRM'"),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM rd_requirement_actor WHERE active AND role = 'ACCEPT' "
            "GROUP BY requirement_id HAVING COUNT(*) > 1)"
        )
    ):
        raise RuntimeError("Multiple active acceptance people exist; refuse lossy downgrade")
    op.drop_index("uq_requirement_single_actor_role", table_name="rd_requirement_actor")
    op.create_index(
        "uq_requirement_single_actor_role",
        "rd_requirement_actor",
        ["requirement_id", "role"],
        unique=True,
        postgresql_where=sa.text("active AND role IN ('CONFIRM', 'ACCEPT')"),
    )

"""Issue 4 metadata and multiple confirmers; stop writers before MySQL DDL."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "mysql57_0012"
down_revision = "mysql57_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_requirement_single_actor_role", table_name="rd_requirement_actor")
    op.drop_column("rd_requirement_actor", "single_actor_role")
    op.add_column(
        "rd_requirement",
        sa.Column("description_format", sa.String(8), nullable=False, server_default="PLAIN"),
    )
    for table, name in (("rd_requirement", "requirement"), ("rd_feedback", "feedback")):
        op.add_column(table, sa.Column("deleted_at", mysql.DATETIME(fsp=6), nullable=True))
        op.add_column(table, sa.Column("deleted_by", sa.BigInteger(), nullable=True))
        op.create_foreign_key(f"fk_{name}_deleted_by", table, "sys_user", ["deleted_by"], ["id"])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM rd_requirement_actor "
            "WHERE active = 1 AND role = 'CONFIRM' "
            "GROUP BY requirement_id HAVING COUNT(*) > 1)"
        )
    ):
        raise RuntimeError("Multiple active confirmers exist; refuse lossy downgrade")
    if connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM rd_requirement WHERE description_format <> 'PLAIN' "
            "OR deleted_at IS NOT NULL OR deleted_by IS NOT NULL"
        )
    ) or connection.scalar(
        sa.text(
            "SELECT COUNT(*) FROM rd_feedback "
            "WHERE deleted_at IS NOT NULL OR deleted_by IS NOT NULL"
        )
    ):
        raise RuntimeError("Rich text or soft-deleted records exist; refuse lossy downgrade")
    for table, name in (("rd_requirement", "requirement"), ("rd_feedback", "feedback")):
        op.drop_constraint(f"fk_{name}_deleted_by", table, type_="foreignkey")
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")
    op.drop_column("rd_requirement", "description_format")
    op.add_column(
        "rd_requirement_actor",
        sa.Column(
            "single_actor_role",
            sa.String(16),
            sa.Computed(
                "CASE WHEN active = 1 AND role = 'CONFIRM' THEN role ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_requirement_single_actor_role",
        "rd_requirement_actor",
        ["requirement_id", "single_actor_role"],
    )

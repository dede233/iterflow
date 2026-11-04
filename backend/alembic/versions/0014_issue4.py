"""Multiple confirmers, explicit description format and reversible soft-delete metadata."""

import sqlalchemy as sa

from alembic import op

revision = "0014_issue4"
down_revision = "0013_mail_notice"
branch_labels = None
depends_on = None


def upgrade():
    # Earlier workflow revisions update rows in this same migration transaction.
    # Validate queued deferred integrity triggers before changing their tables.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.drop_index("uq_requirement_single_actor_role", table_name="rd_requirement_actor")
    op.add_column(
        "rd_requirement",
        sa.Column("description_format", sa.String(8), nullable=False, server_default="PLAIN"),
    )
    for table, name in (("rd_requirement", "requirement"), ("rd_feedback", "feedback")):
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by", sa.BigInteger(), nullable=True))
        op.create_foreign_key(f"fk_{name}_deleted_by", table, "sys_user", ["deleted_by"], ["id"])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM rd_requirement_actor WHERE active AND role = 'CONFIRM' "
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
    op.create_index(
        "uq_requirement_single_actor_role",
        "rd_requirement_actor",
        ["requirement_id", "role"],
        unique=True,
        postgresql_where=sa.text("active AND role = 'CONFIRM'"),
    )

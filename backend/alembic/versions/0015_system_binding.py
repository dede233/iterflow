"""Single-system versions; preserve legacy rows without inferred ownership."""

import sqlalchemy as sa

from alembic import op

revision = "0015_system_binding"
down_revision = "0014_issue4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rd_version", sa.Column("system_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_version_system", "rd_version", "sys_business_system", ["system_id"], ["id"]
    )
    op.create_index("ix_rd_version_system_id", "rd_version", ["system_id"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM rd_version WHERE system_id IS NOT NULL")):
        raise RuntimeError("System bindings exist; refuse lossy downgrade")
    op.drop_index("ix_rd_version_system_id", table_name="rd_version")
    op.drop_constraint("fk_version_system", "rd_version", type_="foreignkey")
    op.drop_column("rd_version", "system_id")

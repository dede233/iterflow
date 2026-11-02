"""Allow multiple acceptance people in MySQL 5.7; stop writers before DDL."""

import sqlalchemy as sa

from alembic import op

revision = "mysql57_0010"
down_revision = "mysql57_0009"
branch_labels = None
depends_on = None


def upgrade():
    # Retain the unique index and change only its generated key. No actor rows are removed.
    op.execute(
        "ALTER TABLE rd_requirement_actor MODIFY COLUMN single_actor_role VARCHAR(16) "
        "GENERATED ALWAYS AS (CASE WHEN active = 1 AND role = 'CONFIRM' "
        "THEN role ELSE NULL END) STORED"
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM rd_requirement_actor WHERE active = 1 "
            "AND role = 'ACCEPT' "
            "GROUP BY requirement_id HAVING COUNT(*) > 1)"
        )
    ):
        raise RuntimeError("Multiple active acceptance people exist; refuse lossy downgrade")
    op.execute(
        "ALTER TABLE rd_requirement_actor MODIFY COLUMN single_actor_role VARCHAR(16) "
        "GENERATED ALWAYS AS (CASE WHEN active = 1 AND role IN ('CONFIRM', 'ACCEPT') "
        "THEN role ELSE NULL END) STORED"
    )

"""Protect seeded roles with an explicit system-role flag.

Revision ID: 0003_role_system_flag
Revises: 0002_refresh_sessions
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_role_system_flag"
down_revision: str | None = "0002_refresh_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SYSTEM_ROLE_CODES = (
    "MEMBER",
    "CUSTOMER_SERVICE_OPERATIONS",
    "PRODUCT_MANAGER",
    "DEVELOPMENT_LEAD",
    "TESTER",
    "SUPER_ADMIN",
)


def upgrade() -> None:
    op.add_column(
        "sys_role",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    quoted_codes = ", ".join(f"'{code}'" for code in SYSTEM_ROLE_CODES)
    op.execute(sa.text(f"UPDATE sys_role SET is_system = true WHERE code IN ({quoted_codes})"))


def downgrade() -> None:
    op.drop_column("sys_role", "is_system")

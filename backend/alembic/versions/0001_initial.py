"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-20
"""
from alembic import op
from sqlalchemy import text
from app.core.database import Base
from app.models import entities  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_feedback_primary_relation ON rd_requirement_feedback(feedback_id) WHERE is_primary = true")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_requirement_active_version ON rd_version_requirement(requirement_id) WHERE active = true")


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

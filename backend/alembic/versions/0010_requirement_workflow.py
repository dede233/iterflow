"""Simplify requirement workflow while preserving historical completion."""

from uuid import uuid4
from datetime import UTC

from alembic import op
import sqlalchemy as sa

revision = "0010_requirement_workflow"
down_revision = "0009_collaboration_people"
branch_labels = None
depends_on = None


def utc_iso(value):
    if value is None:
        return None
    # MySQL DATETIME is stored in UTC without tzinfo; PostgreSQL may return
    # aware values in the connection's configured time zone.
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def upgrade():
    op.add_column(
        "rd_requirement",
        sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("rd_requirement", sa.Column("confirmed_revision", sa.Integer()))
    op.add_column(
        "rd_requirement",
        sa.Column(
            "legacy_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "rd_requirement",
        sa.Column("design_status", sa.String(20), nullable=False, server_default="NOT_REQUIRED"),
    )
    op.add_column("rd_requirement", sa.Column("paused_from", sa.String(20)))
    op.create_table(
        "rd_requirement_step",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "requirement_id", sa.BigInteger(), sa.ForeignKey("rd_requirement.id"), nullable=False
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_rd_requirement_step_requirement_id", "rd_requirement_step", ["requirement_id"]
    )
    conn = op.get_bind()
    steps = sa.table(
        "rd_requirement_step",
        sa.column("id"),
        sa.column("requirement_id"),
        sa.column("action"),
        sa.column("actor_id"),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("detail", sa.JSON()),
    )
    for row in conn.execute(sa.text("SELECT id, status, owner_id FROM rd_requirement")):
        people = (
            conn.execute(
                sa.text(
                    "SELECT user_id, discipline, completed_at FROM rd_requirement_participant WHERE requirement_id=:id"
                ),
                {"id": row.id},
            )
            .mappings()
            .all()
        )
        detail = {
            "original_status": row.status,
            "legacy_owner_id": row.owner_id,
            "legacy_developers": [
                {
                    **dict(p),
                    "completed_at": utc_iso(p["completed_at"]),
                }
                for p in people
            ],
        }
        conn.execute(
            steps.insert().values(
                id=str(uuid4()),
                requirement_id=row.id,
                action="LEGACY_MIGRATION",
                actor_id=None,
                created_at=sa.func.current_timestamp(),
                detail=detail,
            )
        )
    conn.execute(
        sa.text(
            "UPDATE rd_requirement SET confirmed_revision=1 WHERE status NOT IN ('DRAFT', 'CANCELED')"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE rd_requirement SET legacy_completed=true WHERE status IN ('DONE', 'ONLINE')"
        )
    )
    conn.execute(
        sa.text("UPDATE rd_requirement SET design_status='IN_PROGRESS' WHERE status='DESIGNING'")
    )
    conn.execute(
        sa.text(
            "UPDATE rd_requirement SET status='CONFIRMED', revision=revision+1 WHERE status IN ('PLANNED','DESIGNING')"
        )
    )


def downgrade():
    raise RuntimeError(
        "Workflow history requires a reviewed recovery; automatic downgrade is disabled"
    )

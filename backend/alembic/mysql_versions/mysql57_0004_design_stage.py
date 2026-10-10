"""Expand the effective MySQL status guard with no unguarded DML interval."""

from sqlalchemy import text

from alembic import op

revision = "mysql57_0004"
down_revision = "mysql57_0003"
branch_labels = None
depends_on = None

OLD = "('DRAFT','CONFIRMED','PLANNED','DEVELOPING','TESTING','DONE','ONLINE','PAUSED','CANCELED')"
NEW = (
    "('DRAFT','CONFIRMED','PLANNED','DESIGNING','DEVELOPING',"
    "'TESTING','DONE','ONLINE','PAUSED','CANCELED')"
)


def upgrade():
    bind = op.get_bind()
    statements = {}
    for event in ("insert", "update"):
        name = "domain_rd_requirement_" + event
        body = bind.scalar(
            text(
                "SELECT ACTION_STATEMENT FROM information_schema.triggers "
                "WHERE trigger_schema=DATABASE() AND trigger_name=:name"
            ),
            {"name": name},
        )
        clause = "BINARY NEW.`status` NOT IN " + OLD
        if (
            not body
            or body.count(clause) != 1
            or any(
                marker not in body
                for marker in (
                    "@@foreign_key_checks",
                    "@@unique_checks",
                    "invalid rd_requirement.requirement_no",
                    "invalid rd_requirement.source",
                    "invalid rd_requirement.priority",
                    "invalid rd_requirement.status",
                )
            )
        ):
            raise RuntimeError(
                "Requirement guard differs from expected baseline; inspect before DDL"
            )
        statements[event] = body.replace(clause, "BINARY NEW.`status` NOT IN " + NEW)
    for event, body in statements.items():
        name = "domain_rd_requirement_" + event
        guard = "design_stage_guard_" + event
        # MySQL 5.7 supports multiple BEFORE triggers. Install full guard before
        # swapping the old named trigger, so failed DDL cannot leave DML unprotected.
        bind.execute(
            text(
                f"CREATE TRIGGER `{guard}` BEFORE {event.upper()} ON "
                f"rd_requirement FOR EACH ROW {body}"
            )
        )
        bind.execute(text(f"DROP TRIGGER `{name}`"))
        bind.execute(
            text(
                f"CREATE TRIGGER `{name}` BEFORE {event.upper()} ON "
                f"rd_requirement FOR EACH ROW {body}"
            )
        )
        bind.execute(text(f"DROP TRIGGER `{guard}`"))


def downgrade():
    raise RuntimeError("Design state is business history; destructive downgrade refused")

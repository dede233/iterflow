"""Add UTC microsecond confirmations with effective MySQL 5.7 domain guards."""

from sqlalchemy import text

from alembic import op

revision = "mysql57_0005"
down_revision = "mysql57_0004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    for event in ("insert", "update", "delete"):
        body = bind.scalar(
            text(
                "SELECT ACTION_STATEMENT FROM information_schema.triggers "
                "WHERE trigger_schema=DATABASE() AND trigger_name=:name"
            ),
            {"name": "domain_rd_requirement_participant_" + event},
        )
        if not body or "@@foreign_key_checks" not in body or "@@unique_checks" not in body:
            raise RuntimeError("Participant guards differ from baseline; inspect before DDL")
    # Application writes must be stopped for this non-transactional MySQL DDL.
    # Existing rows deliberately remain unconfirmed, never auto-approved.
    bind.execute(
        text("ALTER TABLE rd_requirement_participant ADD COLUMN completed_at DATETIME(6) NULL")
    )
    for event in ("insert", "update"):
        bind.execute(
            text(f"""CREATE TRIGGER completion_rd_requirement_participant_{event}
        BEFORE {event.upper()} ON rd_requirement_participant FOR EACH ROW BEGIN
        IF NEW.completed_at IS NOT NULL AND BINARY NEW.discipline <> 'DEVELOPMENT' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid design completion';
        END IF;
        END""")
        )


def downgrade():
    raise RuntimeError(
        "Developer confirmations are business history; destructive downgrade refused"
    )

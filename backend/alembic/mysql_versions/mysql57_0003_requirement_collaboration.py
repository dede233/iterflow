"""MySQL 5.7 collaboration with effective domain and foreign-key guards."""

import runpy
from pathlib import Path

from sqlalchemy import text

from alembic import op

revision = "mysql57_0003"
down_revision = "mysql57_0002"
branch_labels = None
depends_on = None


def upgrade():
    helpers = runpy.run_path(str(Path(__file__).parents[1] / "requirement_collaboration_v1.py"))
    helpers["validate_role_codes"](op.get_bind())
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("MySQL migration requires MySQL")
    bind.execute(
        text("""CREATE TABLE rd_requirement_participant (
        requirement_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        discipline VARCHAR(11) NOT NULL,
        PRIMARY KEY (requirement_id, user_id, discipline),
        CONSTRAINT fk_participant_requirement FOREIGN KEY (requirement_id)
            REFERENCES rd_requirement(id) ON DELETE RESTRICT,
        CONSTRAINT fk_participant_user FOREIGN KEY (user_id)
            REFERENCES sys_user(id) ON DELETE RESTRICT,
        INDEX ix_requirement_participant_user (user_id)
    ) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARSET=utf8mb4 COLLATE=utf8mb4_bin""")
    )
    for event in ("insert", "update", "delete"):
        domain = (
            ""
            if event == "delete"
            else """
            IF BINARY NEW.discipline NOT IN ('DEVELOPMENT','DESIGN') OR
                OCTET_LENGTH(NEW.discipline) NOT IN (6,11) THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid participant discipline';
            END IF;"""
        )
        bind.execute(
            text(f"""CREATE TRIGGER domain_rd_requirement_participant_{event}
            BEFORE {event.upper()} ON rd_requirement_participant FOR EACH ROW BEGIN
            IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks';
            END IF;
            {domain}
            END""")
        )
    runpy.run_path(str(Path(__file__).parents[1] / "requirement_collaboration_v1.py"))["add_roles"](
        bind
    )


def downgrade():
    raise RuntimeError("Collaboration contains business assignments; destructive downgrade refused")

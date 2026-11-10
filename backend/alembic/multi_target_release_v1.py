"""Frozen three-table release-target migration shared by the two DB paths."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade(op, *, is_mysql):
    timestamp = mysql.DATETIME(fsp=6) if is_mysql else sa.DateTime(timezone=True)
    code = mysql.VARBINARY(256) if is_mysql else sa.String(64)
    options = (
        dict(
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
            mysql_collate="utf8mb4_bin",
            mysql_row_format="DYNAMIC",
        )
        if is_mysql
        else {}
    )

    def audit():
        return [
            sa.Column("created_at", timestamp, nullable=False),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("updated_at", timestamp, nullable=False),
            sa.Column("updated_by", sa.BigInteger()),
            sa.Column("revision", sa.Integer(), nullable=False),
        ]

    op.add_column(
        "rd_version",
        sa.Column("release_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "sys_release_target",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "system_id", sa.BigInteger(), sa.ForeignKey("sys_business_system.id"), nullable=False
        ),
        sa.Column("code", code, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("app_id", sa.String(64)),
        sa.Column("url", sa.String(500)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *audit(),
        sa.UniqueConstraint("system_id", "code", name="uq_release_target_system_code"),
        sa.CheckConstraint(
            "platform IN ('PC_WEB','WECHAT_MINI_PROGRAM')", name="release_target_platform"
        ),
        **options,
    )
    op.create_index("ix_sys_release_target_system_id", "sys_release_target", ["system_id"])
    initial = (
        [
            sa.Column(
                "initial_version_id",
                sa.BigInteger(),
                sa.Computed(
                    "IF(kind = 'INITIAL' AND status <> 'CANCELED', version_id, NULL)",
                    persisted=True,
                ),
            )
        ]
        if is_mysql
        else []
    )
    op.create_table(
        "rd_release_batch",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("version_id", sa.BigInteger(), sa.ForeignKey("rd_version.id"), nullable=False),
        sa.Column(
            "system_id", sa.BigInteger(), sa.ForeignKey("sys_business_system.id"), nullable=False
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("release_notes", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(500)),
        *audit(),
        *initial,
        sa.CheckConstraint(
            "kind IN ('INITIAL','SUPPLEMENT','REPUBLISH')", name="release_batch_kind"
        ),
        sa.CheckConstraint(
            "status IN ('PLANNED','IN_PROGRESS','COMPLETED','CANCELED')",
            name="release_batch_status",
        ),
        **options,
    )
    op.create_index("ix_rd_release_batch_version_id", "rd_release_batch", ["version_id"])
    op.create_index(
        "uq_release_batch_initial",
        "rd_release_batch",
        ["initial_version_id"] if is_mysql else ["version_id"],
        unique=True,
        **(
            {}
            if is_mysql
            else {"postgresql_where": sa.text("kind = 'INITIAL' AND status <> 'CANCELED'")}
        ),
    )
    op.create_table(
        "rd_release_batch_target",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "batch_id", sa.BigInteger(), sa.ForeignKey("rd_release_batch.id"), nullable=False
        ),
        sa.Column(
            "target_id", sa.BigInteger(), sa.ForeignKey("sys_release_target.id"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", code, nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("app_id", sa.String(64)),
        sa.Column("url", sa.String(500)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("removed_reason", sa.String(500)),
        sa.Column("completed_at", timestamp),
        sa.Column("recorded_at", timestamp),
        sa.Column("completed_by", sa.BigInteger(), sa.ForeignKey("sys_user.id")),
        sa.Column("operator_name", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("evidence", sa.String(1000)),
        *audit(),
        sa.UniqueConstraint("batch_id", "target_id", name="uq_release_batch_target"),
        sa.CheckConstraint(
            "platform IN ('PC_WEB','WECHAT_MINI_PROGRAM')", name="release_batch_target_platform"
        ),
        sa.CheckConstraint(
            "(completed_at IS NULL AND recorded_at IS NULL AND completed_by IS NULL) OR (completed_at IS NOT NULL AND recorded_at IS NOT NULL AND completed_by IS NOT NULL)",
            name="release_target_completion",
        ),
        **options,
    )
    op.create_index("ix_rd_release_batch_target_batch_id", "rd_release_batch_target", ["batch_id"])
    op.create_index(
        "ix_rd_release_batch_target_target_id", "rd_release_batch_target", ["target_id"]
    )
    if is_mysql:
        domains = {
            "sys_release_target": "NEW.enabled NOT IN (0,1) OR NEW.platform NOT IN ('PC_WEB','WECHAT_MINI_PROGRAM')",
            "rd_release_batch": "NEW.kind NOT IN ('INITIAL','SUPPLEMENT','REPUBLISH') OR NEW.status NOT IN ('PLANNED','IN_PROGRESS','COMPLETED','CANCELED')",
            "rd_release_batch_target": "NEW.active NOT IN (0,1) OR NEW.platform NOT IN ('PC_WEB','WECHAT_MINI_PROGRAM') OR (NEW.completed_at IS NULL) <> (NEW.recorded_at IS NULL) OR (NEW.completed_at IS NULL) <> (NEW.completed_by IS NULL)",
        }
        for table, condition in domains.items():
            for event in ("insert", "update", "delete"):
                domain = (
                    ""
                    if event == "delete"
                    else f"IF {condition} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid target release domain'; END IF;"
                )
                op.execute(
                    f"CREATE TRIGGER domain_{table}_{event} BEFORE {event.upper()} ON {table} FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; END IF; {domain} END"
                )
        for event in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER immutable_release_target_{event} BEFORE {event.upper()} ON rd_release_batch_target FOR EACH ROW BEGIN IF OLD.completed_at IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='completed target record is immutable'; END IF; END"
            )
        op.execute(
            "CREATE TRIGGER frozen_release_version_insert BEFORE INSERT ON rd_version FOR EACH ROW BEGIN IF NEW.release_frozen NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid release freeze'; END IF; END"
        )
        op.execute(
            "CREATE TRIGGER frozen_release_version_update BEFORE UPDATE ON rd_version FOR EACH ROW BEGIN IF NEW.release_frozen NOT IN (0,1) OR (OLD.release_frozen = 1 AND NEW.release_frozen <> 1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='release freeze is irreversible'; END IF; END"
        )
    else:
        op.execute(
            "CREATE FUNCTION iterflow_protect_target_success() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.completed_at IS NOT NULL THEN RAISE EXCEPTION 'completed target record is immutable' USING ERRCODE='23514'; END IF; IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$"
        )
        op.execute(
            "CREATE TRIGGER immutable_release_target BEFORE UPDATE OR DELETE ON rd_release_batch_target FOR EACH ROW EXECUTE FUNCTION iterflow_protect_target_success()"
        )
        op.execute(
            "CREATE FUNCTION iterflow_protect_release_freeze() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.release_frozen AND NOT NEW.release_frozen THEN RAISE EXCEPTION 'release freeze is irreversible' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"
        )
        op.execute(
            "CREATE TRIGGER frozen_release_version BEFORE UPDATE ON rd_version FOR EACH ROW EXECUTE FUNCTION iterflow_protect_release_freeze()"
        )


def downgrade(op, *, is_mysql):
    connection = op.get_bind()
    for table in ("sys_release_target", "rd_release_batch", "rd_release_batch_target"):
        if connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}")):
            raise RuntimeError("Target release history exists; refuse lossy downgrade")
    if connection.scalar(sa.text("SELECT COUNT(*) FROM rd_version WHERE release_frozen = true")):
        raise RuntimeError("Release freeze exists; refuse lossy downgrade")
    if is_mysql:
        for event in ("insert", "update"):
            op.execute(f"DROP TRIGGER frozen_release_version_{event}")
    else:
        op.execute("DROP TRIGGER frozen_release_version ON rd_version")
        op.execute("DROP FUNCTION iterflow_protect_release_freeze()")
    for table in ("rd_release_batch_target", "rd_release_batch", "sys_release_target"):
        op.drop_table(table)
    if not is_mysql:
        op.execute("DROP FUNCTION iterflow_protect_target_success()")
    op.drop_column("rd_version", "release_frozen")

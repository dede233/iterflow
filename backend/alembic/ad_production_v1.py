"""Frozen schema and additive permissions for ad production."""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

TABLE = "ops_ad_production"
STATUSES = ("NOT_STARTED", "IN_PROGRESS", "SHIPPING", "COMPLETED")
PERMISSIONS = {
    "ops.ad_production.view": "查看广告制作",
    "ops.ad_production.create": "新建广告制作",
    "ops.ad_production.edit": "编辑广告制作",
}


def _add_permissions(connection, *, is_mysql):
    metadata = sa.MetaData()
    permission = sa.Table("sys_permission", metadata, autoload_with=connection)
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)

    def encode(code):
        return code.encode("utf-8") if is_mysql else code

    admin = connection.execute(
        sa.select(role.c.id, role.c.revision)
        .where(
            role.c.code == encode("SUPER_ADMIN"),
            role.c.is_system.is_(True),
            role.c.enabled.is_(True),
        )
        .with_for_update()
    ).one_or_none()
    names = {encode(code): name for code, name in PERMISSIONS.items()}
    permissions = dict(
        connection.execute(
            sa.select(permission.c.code, permission.c.id).where(permission.c.code.in_(names))
        ).all()
    )
    for code, name in names.items():
        if code not in permissions:
            result = connection.execute(
                permission.insert().values(code=code, name=name, category="BUTTON")
            )
            permissions[code] = result.inserted_primary_key[0]

    # The fresh install seed assigns these permissions after creating the administrator.
    if admin is None:
        return
    role_id, revision = admin
    before_ids = set(
        connection.scalars(sa.select(link.c.permission_id).where(link.c.role_id == role_id))
    )
    additions = set(permissions.values()) - before_ids
    if not additions:
        return
    now = datetime.now(UTC)
    if is_mysql:
        now = now.replace(tzinfo=None)
    result = connection.execute(
        role.update()
        .where(role.c.id == role_id, role.c.revision == revision)
        .values(updated_at=now, updated_by=None, revision=revision + 1)
    )
    if result.rowcount != 1:
        raise RuntimeError("Super administrator role revision changed during permission migration")
    connection.execute(
        link.insert(),
        [
            {"role_id": role_id, "permission_id": permission_id}
            for permission_id in sorted(additions)
        ],
    )
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    connection.execute(
        audit.insert().values(
            entity_type="ROLE",
            entity_id=role_id,
            action="ROLE_PERMISSION_UPDATE",
            operator_id=None,
            request_id="migration-ad-production-v1",
            before_data={"permission_ids": sorted(before_ids), "revision": revision},
            after_data={"permission_ids": sorted(before_ids | additions), "revision": revision + 1},
            created_at=now,
        )
    )


def upgrade(op, *, is_mysql):
    timestamp = mysql.DATETIME(fsp=6) if is_mysql else sa.DateTime(timezone=True)
    options = (
        {
            "mysql_engine": "InnoDB",
            "mysql_row_format": "DYNAMIC",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_bin",
        }
        if is_mysql
        else {}
    )
    status = sa.Enum(
        *STATUSES, name="ad_production_status", native_enum=False, create_constraint=True, length=16
    )
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("issuer", sa.String(100), nullable=False),
        sa.Column("status", status, nullable=False, server_default="NOT_STARTED"),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.Column("updated_by", sa.BigInteger()),
        sa.Column("revision", sa.Integer(), nullable=False),
        **options,
    )
    op.create_index("ix_ad_production_work_date_id", TABLE, ["work_date", "id"])
    op.create_index(
        "ix_ad_production_creator_work_date_id", TABLE, ["created_by", "work_date", "id"]
    )
    if is_mysql:
        allowed = ", ".join(f"'{status}'" for status in STATUSES)
        for event in ("insert", "update", "delete"):
            domain_check = (
                f"IF BINARY NEW.status NOT IN ({allowed}) THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid ops_ad_production.status'; "
                "END IF; "
                if event != "delete"
                else ""
            )
            op.execute(
                f"CREATE TRIGGER domain_{TABLE}_{event} BEFORE {event.upper()} ON {TABLE} "
                "FOR EACH ROW BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN "
                "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IterFlow requires integrity checks'; "
                f"END IF; {domain_check}END"
            )
    _add_permissions(op.get_bind(), is_mysql=is_mysql)


def downgrade(op):
    connection = op.get_bind()
    queries = (
        f"SELECT 1 FROM {TABLE} LIMIT 1",
        "SELECT 1 FROM sys_attachment_relation "
        "WHERE entity_type IN ('AD_PRODUCTION', 'AD_PRODUCTION_ARCHIVED') LIMIT 1",
        "SELECT 1 FROM sys_operation_log WHERE entity_type = 'AD_PRODUCTION' LIMIT 1",
    )
    if any(connection.scalar(sa.text(query)) for query in queries):
        raise RuntimeError(
            "Ad production records, attachments or audit history exist; downgrade refused"
        )
    # Keep the permission catalog and grants so role configuration survives a schema downgrade.
    op.drop_table(TABLE)

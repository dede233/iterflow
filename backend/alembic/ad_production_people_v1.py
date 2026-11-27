"""Add ad production people and frozen, additive role grants."""

from datetime import UTC, datetime

import sqlalchemy as sa

TABLE = "ops_ad_production"
PEOPLE_COLUMNS = (
    (
        "receiver_id",
        "fk_ad_production_receiver",
        "ix_ad_production_receiver_work_date_id",
        ("receiver_id", "work_date", "id"),
    ),
    (
        "completed_by_id",
        "fk_ad_production_completed_by",
        "ix_ad_production_completed_by_id",
        ("completed_by_id",),
    ),
)
CREATOR_CODE = "AD_PRODUCTION_CREATOR"
CREATOR_NAME = "广告制作提交人"
ROLE_GRANTS = {
    CREATOR_CODE: ("ops.ad_production.view", "ops.ad_production.create"),
    "DESIGNER": ("ops.ad_production.view", "ops.ad_production.edit"),
}
REQUEST_ID = "migration-ad-production-people-v1"


def upgrade(op):
    connection = op.get_bind()
    metadata = sa.MetaData()
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    permission = sa.Table("sys_permission", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    is_mysql = connection.dialect.name == "mysql"

    def encode(value):
        return value.encode("utf-8") if is_mysql else value

    creator_code = encode(CREATOR_CODE)
    creator_is_system = connection.scalar(
        sa.select(role.c.is_system).where(role.c.code == creator_code)
    )
    if creator_is_system is not None and not creator_is_system:
        raise RuntimeError(
            "AD_PRODUCTION_CREATOR belongs to a custom role; inspect before migration"
        )
    # Check prerequisites before any MySQL DDL, which implicitly commits.
    codes = {encode(code) for grants in ROLE_GRANTS.values() for code in grants}
    permission_ids = dict(
        connection.execute(
            sa.select(permission.c.code, permission.c.id).where(permission.c.code.in_(codes))
        ).all()
    )
    if permission_ids.keys() != codes:
        raise RuntimeError(
            "Ad production permission catalog is incomplete; inspect before migration"
        )

    for field, foreign_key, index, index_columns in PEOPLE_COLUMNS:
        op.add_column(TABLE, sa.Column(field, sa.BigInteger(), nullable=True))
        op.create_index(index, TABLE, index_columns)
        op.create_foreign_key(foreign_key, TABLE, "sys_user", [field], ["id"], ondelete="RESTRICT")

    roles = {
        row["code"]: row
        for row in connection.execute(
            sa.select(role)
            .where(role.c.code.in_([encode(code) for code in ROLE_GRANTS]))
            .order_by(role.c.id)
            .with_for_update()
        ).mappings()
    }
    now = datetime.now(UTC)
    if is_mysql:
        now = now.replace(tzinfo=None)
    for code, grants in ROLE_GRANTS.items():
        current = roles.get(encode(code))
        desired = {permission_ids[encode(grant)] for grant in grants}
        if current is None:
            if code != CREATOR_CODE:
                continue
            profile = {
                "name": CREATOR_NAME,
                "data_scope": "SELF",
                "is_system": True,
                "enabled": True,
                "revision": 1,
            }
            result = connection.execute(
                role.insert().values(code=creator_code, created_at=now, updated_at=now, **profile)
            )
            role_id = result.inserted_primary_key[0]
            additions = desired
            action = "ROLE_CREATE"
            before = None
            after = {
                "id": role_id,
                "code": CREATOR_CODE,
                "permission_ids": sorted(desired),
                **profile,
            }
        else:
            if not current["is_system"] or not current["enabled"]:
                continue
            role_id, revision = current["id"], current["revision"]
            before_ids = set(
                connection.scalars(sa.select(link.c.permission_id).where(link.c.role_id == role_id))
            )
            additions = desired - before_ids
            if not additions:
                continue
            result = connection.execute(
                role.update()
                .where(role.c.id == role_id, role.c.revision == revision)
                .values(revision=revision + 1, updated_at=now, updated_by=None)
            )
            if result.rowcount != 1:
                raise RuntimeError(
                    "Role revision changed during ad production permission migration"
                )
            action = "ROLE_PERMISSION_UPDATE"
            before = {"permission_ids": sorted(before_ids), "revision": revision}
            after = {"permission_ids": sorted(before_ids | additions), "revision": revision + 1}
        connection.execute(
            link.insert(),
            [
                {"role_id": role_id, "permission_id": permission_id}
                for permission_id in sorted(additions)
            ],
        )
        connection.execute(
            audit.insert().values(
                entity_type="ROLE",
                entity_id=role_id,
                action=action,
                operator_id=None,
                request_id=REQUEST_ID,
                before_data=before,
                after_data=after,
                created_at=now,
            )
        )


def downgrade(op):
    connection = op.get_bind()
    people_exist = connection.scalar(
        sa.text(
            f"SELECT 1 FROM {TABLE} "
            "WHERE receiver_id IS NOT NULL OR completed_by_id IS NOT NULL LIMIT 1"
        )
    )
    if people_exist:
        raise RuntimeError("Ad production receiver or completer history exists; downgrade refused")
    # Retain accounts, role grants, and audit history across a schema rollback.
    for field, foreign_key, index, _ in reversed(PEOPLE_COLUMNS):
        op.drop_constraint(foreign_key, TABLE, type_="foreignkey")
        op.drop_index(index, table_name=TABLE)
        op.drop_column(TABLE, field)

"""Add approved operations grants to eligible built-in roles."""

from datetime import UTC, datetime

import sqlalchemy as sa

ROLE_GRANTS = {
    "CUSTOMER_SERVICE_OPERATIONS": {
        f"ops.{area}.{action}"
        for area in ("ad_production", "merchant_ad")
        for action in ("view", "create")
    },
    "DESIGNER": {
        f"ops.{area}.{action}"
        for area in ("ad_production", "merchant_ad")
        for action in ("view", "create", "edit")
    },
}
REQUEST_ID = "migration-ops-role-defaults-v1"
ROLLBACK_ID = REQUEST_ID + "-downgrade"


def _migration_grants(connection, audit, role_id):
    latest = connection.execute(
        sa.select(audit.c.request_id, audit.c.before_data, audit.c.after_data)
        .where(
            audit.c.entity_type == "ROLE",
            audit.c.entity_id == role_id,
            audit.c.action == "ROLE_PERMISSION_UPDATE",
            audit.c.operator_id.is_(None),
            audit.c.request_id.in_((REQUEST_ID, ROLLBACK_ID)),
        )
        .order_by(audit.c.id.desc())
        .limit(1)
    ).one_or_none()
    if latest is None or latest.request_id == ROLLBACK_ID:
        return set()
    return set(latest.after_data["permission_ids"]) - set(latest.before_data["permission_ids"])


def change_grants(connection, *, downgrade=False):
    metadata = sa.MetaData()
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    mysql = connection.dialect.name == "mysql"

    def encode(code):
        return code.encode("utf-8") if mysql else code

    grants = {encode(code): {encode(p) for p in codes} for code, codes in ROLE_GRANTS.items()}
    query = sa.select(role.c.id, role.c.code, role.c.revision).where(
        role.c.code.in_(grants), role.c.is_system.is_(True)
    )
    if not downgrade:
        query = query.where(role.c.enabled.is_(True))
    roles = connection.execute(query.order_by(role.c.id).with_for_update()).all()
    if not roles:
        return

    if not downgrade:
        permission = sa.Table("sys_permission", metadata, autoload_with=connection)
        codes = set.union(*(grants[row.code] for row in roles))
        permission_ids = dict(
            connection.execute(
                sa.select(permission.c.code, permission.c.id)
                .where(permission.c.code.in_(codes))
                .with_for_update()
            ).all()
        )
        if permission_ids.keys() != codes:
            raise RuntimeError("Operations production permission catalog is incomplete")

    now = datetime.now(UTC)
    if mysql:
        now = now.replace(tzinfo=None)
    for role_id, code, revision in roles:
        before_ids = set(
            connection.scalars(sa.select(link.c.permission_id).where(link.c.role_id == role_id))
        )
        if downgrade:
            after_ids = before_ids - _migration_grants(connection, audit, role_id)
        else:
            after_ids = before_ids | {permission_ids[grant] for grant in grants[code]}
        if before_ids == after_ids:
            continue

        result = connection.execute(
            role.update()
            .where(role.c.id == role_id, role.c.revision == revision)
            .values(revision=revision + 1, updated_at=now, updated_by=None)
        )
        if result.rowcount != 1:
            raise RuntimeError("Role revision changed during operations grant migration")
        if downgrade:
            connection.execute(
                link.delete().where(
                    link.c.role_id == role_id, link.c.permission_id.in_(before_ids - after_ids)
                )
            )
        else:
            connection.execute(
                link.insert(),
                [
                    {"role_id": role_id, "permission_id": pid}
                    for pid in sorted(after_ids - before_ids)
                ],
            )
        connection.execute(
            audit.insert().values(
                entity_type="ROLE",
                entity_id=role_id,
                action="ROLE_PERMISSION_UPDATE",
                operator_id=None,
                request_id=ROLLBACK_ID if downgrade else REQUEST_ID,
                before_data={"permission_ids": sorted(before_ids), "revision": revision},
                after_data={"permission_ids": sorted(after_ids), "revision": revision + 1},
                created_at=now,
            )
        )

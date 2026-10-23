"""Frozen, additive 2026-10-23 version permissions; never import mutable seed policy."""

from datetime import UTC, datetime

from sqlalchemy import MetaData, Table, select

ROLE_CODES = ("DEVELOPER", "PRODUCT_MANAGER", "DEVELOPMENT_LEAD")
PERMISSION_CODES = (
    "rd.version.create",
    "rd.version.edit",
    "rd.version.status",
    "rd.version.publish",
)


def upgrade_permissions(bind):
    metadata = MetaData()
    role = Table("sys_role", metadata, autoload_with=bind)
    permission = Table("sys_permission", metadata, autoload_with=bind)
    link = Table("sys_role_permission", metadata, autoload_with=bind)
    audit = Table("sys_operation_log", metadata, autoload_with=bind)
    mysql = bind.dialect.name == "mysql"

    def encoded(value):
        return value.encode("utf-8") if mysql else value

    roles = list(
        bind.execute(
            select(role)
            .where(role.c.code.in_([encoded(c) for c in ROLE_CODES]))
            .order_by(role.c.id)
            .with_for_update()
        ).mappings()
    )
    if any(not r["is_system"] for r in roles):
        raise RuntimeError("Version permission role code belongs to a custom role; inspect first")

    # Fresh migrations create only collaboration roles. Foundation seed has not
    # run yet; updated seed supplies all default grants after migration.
    initialized = (
        bind.scalar(
            select(role.c.id)
            .where(
                role.c.code.in_(
                    [encoded(c) for c in ("SUPER_ADMIN", "PRODUCT_MANAGER", "DEVELOPMENT_LEAD")]
                )
            )
            .limit(1)
        )
        is not None
    )
    if not initialized:
        return
    permissions = dict(
        bind.execute(
            select(permission.c.code, permission.c.id).where(
                permission.c.code.in_([encoded(c) for c in PERMISSION_CODES])
            )
        ).all()
    )
    if len(permissions) != len(PERMISSION_CODES):
        raise RuntimeError("Version permission catalog is incomplete; inspect before migration")

    now = datetime.now(UTC)
    if mysql:
        now = now.replace(tzinfo=None)
    for current in roles:
        role_id = current["id"]
        before_ids = set(
            bind.scalars(select(link.c.permission_id).where(link.c.role_id == role_id))
        )
        additions = set(permissions.values()) - before_ids
        if not additions:
            continue
        result = bind.execute(
            role.update()
            .where(role.c.id == role_id, role.c.revision == current["revision"])
            .values(revision=current["revision"] + 1, updated_at=now, updated_by=None)
        )
        if result.rowcount != 1:
            raise RuntimeError("Role revision changed during permission migration")
        bind.execute(
            link.insert(), [{"role_id": role_id, "permission_id": pid} for pid in sorted(additions)]
        )
        bind.execute(
            audit.insert().values(
                entity_type="ROLE",
                entity_id=role_id,
                action="ROLE_PERMISSION_UPDATE",
                operator_id=None,
                request_id="migration-version-role-permissions-v1",
                before_data={"permission_ids": sorted(before_ids), "revision": current["revision"]},
                after_data={
                    "permission_ids": sorted(before_ids | additions),
                    "revision": current["revision"] + 1,
                    "source": "2026-10-23 version role permission migration",
                },
                created_at=now,
            )
        )

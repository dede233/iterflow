"""Split production permissions without changing existing role or permission IDs."""

from datetime import UTC, datetime

import sqlalchemy as sa

MATERIAL_NAMES = {
    "ops.ad_production.view": ("查看制作需求", "查看物料制作"),
    "ops.ad_production.create": ("发布制作需求", "发布物料制作"),
    "ops.ad_production.edit": ("编辑制作需求", "编辑物料制作"),
}
MERCHANT_NAMES = {
    "ops.merchant_ad.view": "查看商家广告",
    "ops.merchant_ad.create": "发布商家广告",
    "ops.merchant_ad.edit": "编辑商家广告",
}
ROLE_GRANTS = {
    "SUPER_ADMIN": tuple(MERCHANT_NAMES),
    "DESIGNER": ("ops.merchant_ad.view", "ops.merchant_ad.edit"),
    "AD_PRODUCTION_CREATOR": ("ops.merchant_ad.view", "ops.merchant_ad.create"),
    "AD_PRODUCTION_COMPLETER": ("ops.merchant_ad.view", "ops.merchant_ad.edit"),
}
REQUEST_ID = "migration-ops-production-permissions-v1"


def _identifier(connection, value):
    return value.encode("utf-8") if connection.dialect.name == "mysql" else value


def _rename_material(connection, permission, *, downgrade=False):
    names = {_identifier(connection, code): values for code, values in MATERIAL_NAMES.items()}
    rows = connection.execute(
        sa.select(permission.c.id, permission.c.code, permission.c.name)
        .where(permission.c.code.in_(names))
        .with_for_update()
    ).all()
    for permission_id, code, name in rows:
        previous, current = names[code][::-1] if downgrade else names[code]
        if name != previous:
            continue
        connection.execute(
            permission.update().where(permission.c.id == permission_id).values(name=current)
        )


def _read_catalog(connection):
    metadata = sa.MetaData()
    permission = sa.Table("sys_permission", metadata, autoload_with=connection)
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    names = {_identifier(connection, code): name for code, name in MERCHANT_NAMES.items()}
    existing = {
        row.code: row
        for row in connection.execute(
            sa.select(permission).where(permission.c.code.in_(names)).with_for_update()
        )
    }
    return permission, role, link, audit, names, existing


def _grant_ids(connection, permission_ids):
    return {
        _identifier(connection, role_code): {
            permission_ids[code]
            for grant in grants
            if (code := _identifier(connection, grant)) in permission_ids
        }
        for role_code, grants in ROLE_GRANTS.items()
    }


def _has_unexpected_grants(connection, role, link, permission_ids, grants):
    allowed = sa.or_(
        *(
            sa.and_(role.c.code == code, link.c.permission_id.in_(ids))
            for code, ids in grants.items()
        )
    )
    return connection.scalar(
        sa.select(sa.literal(1))
        .select_from(link.join(role))
        .where(
            link.c.permission_id.in_(permission_ids.values()),
            sa.or_(role.c.is_system.is_(False), ~allowed),
        )
        .limit(1)
    )


def _change_grants(connection, role, link, audit, grants, *, remove=False):
    criteria = [role.c.code.in_(grants), role.c.is_system.is_(True)]
    if not remove:
        criteria.append(role.c.enabled.is_(True))
    roles = list(
        connection.execute(
            sa.select(role.c.id, role.c.revision, role.c.code)
            .where(*criteria)
            .order_by(role.c.id)
            .with_for_update()
        )
    )
    now = datetime.now(UTC)
    if connection.dialect.name == "mysql":
        now = now.replace(tzinfo=None)
    for role_id, revision, code in roles:
        before_ids = set(
            connection.scalars(sa.select(link.c.permission_id).where(link.c.role_id == role_id))
        )
        target_ids = grants[code]
        after_ids = before_ids - target_ids if remove else before_ids | target_ids
        if after_ids == before_ids:
            continue
        result = connection.execute(
            role.update()
            .where(role.c.id == role_id, role.c.revision == revision)
            .values(revision=revision + 1, updated_at=now, updated_by=None)
        )
        if result.rowcount != 1:
            raise RuntimeError("Role revision changed during production permission migration")
        if remove:
            connection.execute(
                link.delete().where(link.c.role_id == role_id, link.c.permission_id.in_(target_ids))
            )
        else:
            connection.execute(
                link.insert(),
                [
                    {"role_id": role_id, "permission_id": permission_id}
                    for permission_id in sorted(after_ids - before_ids)
                ],
            )
        before = {
            "revision": revision,
            "permission_ids": sorted(before_ids),
        }
        after = {
            "revision": revision + 1,
            "permission_ids": sorted(after_ids),
        }
        connection.execute(
            audit.insert().values(
                entity_type="ROLE",
                entity_id=role_id,
                action="ROLE_PERMISSION_UPDATE",
                operator_id=None,
                request_id=REQUEST_ID + "-downgrade" if remove else REQUEST_ID,
                before_data=before,
                after_data=after,
                created_at=now,
            )
        )


def upgrade(connection):
    permission, role, link, audit, names, existing = _read_catalog(connection)
    if any(row.name != names[code] or row.category != "BUTTON" for code, row in existing.items()):
        raise RuntimeError(
            "Reserved merchant advertising permission code conflicts with the catalog"
        )
    permission_ids = {code: row.id for code, row in existing.items()}
    if permission_ids and _has_unexpected_grants(
        connection, role, link, permission_ids, _grant_ids(connection, permission_ids)
    ):
        raise RuntimeError("Reserved merchant advertising permission has an unexpected grant")

    for code, name in names.items():
        if code not in permission_ids:
            result = connection.execute(
                permission.insert().values(code=code, name=name, category="BUTTON")
            )
            permission_ids[code] = result.inserted_primary_key[0]
    _rename_material(connection, permission)
    _change_grants(connection, role, link, audit, _grant_ids(connection, permission_ids))


def downgrade(connection):
    # The previous application shares material permissions across both record kinds.
    if connection.scalar(
        sa.text("SELECT 1 FROM ops_ad_production WHERE kind = 'MERCHANT_AD' LIMIT 1")
    ):
        raise RuntimeError(
            "Merchant advertising records exist; production permission downgrade refused"
        )

    permission, role, link, audit, _, existing = _read_catalog(connection)
    permission_ids = {code: row.id for code, row in existing.items()}
    grants = _grant_ids(connection, permission_ids)
    if permission_ids and _has_unexpected_grants(connection, role, link, permission_ids, grants):
        raise RuntimeError(
            "Custom or unexpected merchant advertising grants exist; "
            "production permission downgrade refused"
        )
    # Preserve permission IDs, user-role assignments and all historical audit entries.
    _change_grants(connection, role, link, audit, grants, remove=True)
    _rename_material(connection, permission, downgrade=True)

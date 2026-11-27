"""Rename the default display labels on both supported databases."""

from datetime import UTC, datetime

import sqlalchemy as sa

ROLE_NAMES = {
    "AD_PRODUCTION_CREATOR": ("广告制作发布人", "制作需求发布人"),
    "AD_PRODUCTION_COMPLETER": ("广告制作完成人", "制作需求完成人"),
}
PERMISSION_NAMES = {
    "ops.ad_production.view": ("查看广告制作", "查看制作需求"),
    "ops.ad_production.create": ("新建广告制作", "发布制作需求"),
    "ops.ad_production.edit": ("编辑广告制作", "编辑制作需求"),
}


def rename(connection, *, downgrade=False):
    metadata = sa.MetaData()
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    permission = sa.Table("sys_permission", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    is_mysql = connection.dialect.name == "mysql"
    now = datetime.now(UTC)
    if is_mysql:
        now = now.replace(tzinfo=None)

    def encode(code):
        return code.encode("utf-8") if is_mysql else code

    request_id = "migration-material-production-names-v1"
    if downgrade:
        request_id += "-downgrade"

    for code, names in ROLE_NAMES.items():
        current_name, new_name = names[::-1] if downgrade else names
        current = (
            connection.execute(
                sa.select(role)
                .where(role.c.code == encode(code), role.c.is_system.is_(True))
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if current is None or current["name"] != current_name:
            continue

        role_id, revision = current["id"], current["revision"]
        permission_ids = list(
            connection.scalars(
                sa.select(link.c.permission_id)
                .where(link.c.role_id == role_id)
                .order_by(link.c.permission_id)
            )
        )
        result = connection.execute(
            role.update()
            .where(role.c.id == role_id, role.c.revision == revision)
            .values(name=new_name, revision=revision + 1, updated_at=now, updated_by=None)
        )
        if result.rowcount != 1:
            raise RuntimeError(f"{code} revision changed during material production migration")

        before = {
            "id": role_id,
            "code": code,
            "name": current_name,
            "data_scope": current["data_scope"],
            "enabled": bool(current["enabled"]),
            "is_system": True,
            "revision": revision,
            "permission_ids": permission_ids,
        }
        connection.execute(
            audit.insert().values(
                entity_type="ROLE",
                entity_id=role_id,
                action="ROLE_UPDATE",
                operator_id=None,
                request_id=request_id,
                before_data=before,
                after_data={**before, "name": new_name, "revision": revision + 1},
                created_at=now,
            )
        )

    for code, names in PERMISSION_NAMES.items():
        current_name, new_name = names[::-1] if downgrade else names
        current = connection.execute(
            sa.select(permission.c.id, permission.c.name)
            .where(permission.c.code == encode(code))
            .with_for_update()
        ).one_or_none()
        if current is not None and current.name == current_name:
            connection.execute(
                permission.update().where(permission.c.id == current.id).values(name=new_name)
            )

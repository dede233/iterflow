"""Frozen ad production publisher and completer role defaults."""

from datetime import UTC, datetime

import sqlalchemy as sa

PUBLISHER_CODE = "AD_PRODUCTION_CREATOR"
PUBLISHER_NAME = "广告制作发布人"
COMPLETER_CODE = "AD_PRODUCTION_COMPLETER"
COMPLETER_NAME = "广告制作完成人"
COMPLETER_PERMISSIONS = ("ops.ad_production.view", "ops.ad_production.edit")
REQUEST_ID = "migration-ad-production-roles-v1"


def _permission_ids(connection, link, role_id):
    return list(
        connection.scalars(
            sa.select(link.c.permission_id)
            .where(link.c.role_id == role_id)
            .order_by(link.c.permission_id)
        )
    )


def _audit_role(audit, *, role_id, action, before, after, now):
    return audit.insert().values(
        entity_type="ROLE",
        entity_id=role_id,
        action=action,
        operator_id=None,
        request_id=REQUEST_ID,
        before_data=before,
        after_data=after,
        created_at=now,
    )


def upgrade(connection):
    metadata = sa.MetaData()
    role = sa.Table("sys_role", metadata, autoload_with=connection)
    permission = sa.Table("sys_permission", metadata, autoload_with=connection)
    link = sa.Table("sys_role_permission", metadata, autoload_with=connection)
    audit = sa.Table("sys_operation_log", metadata, autoload_with=connection)
    is_mysql = connection.dialect.name == "mysql"

    def encode(value):
        return value.encode("utf-8") if is_mysql else value

    roles = {
        row["code"]: row
        for row in connection.execute(
            sa.select(role)
            .where(role.c.code.in_([encode(PUBLISHER_CODE), encode(COMPLETER_CODE)]))
            .order_by(role.c.id)
            .with_for_update()
        ).mappings()
    }
    for code in (PUBLISHER_CODE, COMPLETER_CODE):
        current = roles.get(encode(code))
        if current is not None and not current["is_system"]:
            raise RuntimeError(f"{code} belongs to a custom role; inspect before migration")

    publisher = roles.get(encode(PUBLISHER_CODE))
    if publisher is None:
        raise RuntimeError(f"{PUBLISHER_CODE} is missing; inspect before migration")
    completer = roles.get(encode(COMPLETER_CODE))
    completer_permission_ids = sorted(
        connection.scalars(
            sa.select(permission.c.id).where(
                permission.c.code.in_([encode(code) for code in COMPLETER_PERMISSIONS])
            )
        )
    )
    if len(completer_permission_ids) != len(COMPLETER_PERMISSIONS):
        raise RuntimeError(
            "Ad production permission catalog is incomplete; inspect before migration"
        )

    completer_profile = {
        "name": COMPLETER_NAME,
        "data_scope": "SELF",
        "is_system": True,
        "enabled": True,
    }
    if completer is not None and (
        any(completer[key] != value for key, value in completer_profile.items())
        or _permission_ids(connection, link, completer["id"]) != completer_permission_ids
    ):
        raise RuntimeError(f"{COMPLETER_CODE} differs from its default; inspect before migration")

    now = datetime.now(UTC)
    if is_mysql:
        now = now.replace(tzinfo=None)
    if publisher["name"] != PUBLISHER_NAME:
        role_id, revision = publisher["id"], publisher["revision"]
        before = {
            "id": role_id,
            "code": PUBLISHER_CODE,
            "name": publisher["name"],
            "data_scope": publisher["data_scope"],
            "is_system": True,
            "enabled": bool(publisher["enabled"]),
            "revision": revision,
            "permission_ids": _permission_ids(connection, link, role_id),
        }
        result = connection.execute(
            role.update()
            .where(role.c.id == role_id, role.c.revision == revision)
            .values(name=PUBLISHER_NAME, revision=revision + 1, updated_at=now, updated_by=None)
        )
        if result.rowcount != 1:
            raise RuntimeError("Publisher role revision changed during ad production migration")
        connection.execute(
            _audit_role(
                audit,
                role_id=role_id,
                action="ROLE_UPDATE",
                before=before,
                after={**before, "name": PUBLISHER_NAME, "revision": revision + 1},
                now=now,
            )
        )

    if completer is None:
        result = connection.execute(
            role.insert().values(
                code=encode(COMPLETER_CODE),
                revision=1,
                created_at=now,
                updated_at=now,
                **completer_profile,
            )
        )
        role_id = result.inserted_primary_key[0]
        connection.execute(
            link.insert(),
            [
                {"role_id": role_id, "permission_id": permission_id}
                for permission_id in completer_permission_ids
            ],
        )
        connection.execute(
            _audit_role(
                audit,
                role_id=role_id,
                action="ROLE_CREATE",
                before=None,
                after={
                    **completer_profile,
                    "id": role_id,
                    "code": COMPLETER_CODE,
                    "revision": 1,
                    "permission_ids": completer_permission_ids,
                },
                now=now,
            )
        )

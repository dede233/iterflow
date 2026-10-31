"""Frozen additive role definitions for the collaboration migration."""

from datetime import UTC, datetime

from sqlalchemy import MetaData, Table, select


def validate_role_codes(bind):
    role = Table("sys_role", MetaData(), autoload_with=bind)
    codes = ["DEVELOPER", "DESIGNER"]
    if bind.dialect.name == "mysql":
        codes = [value.encode("utf-8") for value in codes]
    if bind.execute(select(role.c.id).where(role.c.code.in_(codes))).first():
        raise RuntimeError("Collaboration role code already exists; inspect before migration")


def add_roles(bind):
    metadata = MetaData()
    role = Table("sys_role", metadata, autoload_with=bind)
    permission = Table("sys_permission", metadata, autoload_with=bind)
    link = Table("sys_role_permission", metadata, autoload_with=bind)
    mysql = bind.dialect.name == "mysql"

    def code(value):
        return value.encode("utf-8") if mysql else value

    now = datetime.now(UTC)
    if mysql:
        now = now.replace(tzinfo=None)
    for role_code, name in [("DEVELOPER", "开发人员"), ("DESIGNER", "设计人员")]:
        existing = bind.execute(select(role.c.id).where(role.c.code == code(role_code))).first()
        if existing:
            raise RuntimeError("Collaboration role code already exists; inspect before migration")
        result = bind.execute(
            role.insert().values(
                code=code(role_code),
                name=name,
                data_scope="SELF",
                enabled=True,
                is_system=True,
                created_at=now,
                updated_at=now,
                revision=1,
            )
        )
        role_id = result.inserted_primary_key[0]
        permission_ids = bind.scalars(
            select(permission.c.id).where(
                permission.c.code.in_(
                    [
                        code(c)
                        for c in [
                            "dashboard.view",
                            "rd.requirement.view",
                            "rd.requirement.status",
                            "rd.version.view",
                            "rd.release.view",
                        ]
                    ]
                )
            )
        )
        for permission_id in permission_ids:
            bind.execute(link.insert().values(role_id=role_id, permission_id=permission_id))

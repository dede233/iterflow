"""Upgrade a populated previous revision, preserving customized role/account state."""

import runpy
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from alembic import command
from app.cli.seed import seed_database
from app.models.entities import (
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)

TARGETS = {"DEVELOPER", "PRODUCT_MANAGER", "DEVELOPMENT_LEAD"}
LEGACY_MISSING = {
    "DEVELOPER": {
        "rd.version.create",
        "rd.version.edit",
        "rd.version.status",
        "rd.version.publish",
    },
    "PRODUCT_MANAGER": {"rd.version.status", "rd.version.publish"},
    "DEVELOPMENT_LEAD": {"rd.version.create", "rd.version.publish"},
}


def exercise_upgrade(engine, cfg, monkeypatch, case):
    mysql = engine.dialect.name == "mysql"
    old = "mysql57_0005" if mysql else "0007_development_completion"
    new = "mysql57_0006" if mysql else "0008_version_role_permissions"
    command.upgrade(cfg, old)
    with Session(engine) as db:
        seed_database(db, username="migration-admin", password="Initial-migration-test!")
        roles = {r.code: r for r in db.scalars(select(Role))}
        perms = {p.code: p.id for p in db.scalars(select(Permission))}
        for code, missing in LEGACY_MISSING.items():
            db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == roles[code].id,
                    RolePermission.permission_id.in_([perms[c] for c in missing]),
                )
            )
        # Existing manual grant must survive, and extra grants must not be removed.
        db.add(
            RolePermission(
                role_id=roles["PRODUCT_MANAGER"].id, permission_id=perms["rd.version.publish"]
            )
        )
        db.add(
            RolePermission(role_id=roles["DEVELOPER"].id, permission_id=perms["rd.feedback.edit"])
        )
        roles["DEVELOPMENT_LEAD"].enabled = False
        custom = Role(code="CUSTOM_DEPLOY", name="既有自定义", is_system=False, data_scope="SELF")
        db.add(custom)
        db.flush()
        db.add(RolePermission(role_id=custom.id, permission_id=perms["rd.version.publish"]))
        admin = db.scalar(select(User).where(User.username == "migration-admin"))
        admin.must_change_password = False
        db.add(UserRole(user_id=admin.id, role_id=roles["DEVELOPER"].id))
        db.add(
            Version(version_no="LEGACY-V1", name="既有版本", owner_id=admin.id, created_by=admin.id)
        )
        if case == "collision":
            roles["PRODUCT_MANAGER"].is_system = False
        if case == "incomplete":
            db.execute(
                delete(RolePermission).where(
                    RolePermission.permission_id == perms["rd.version.publish"]
                )
            )
            db.execute(delete(Permission).where(Permission.id == perms["rd.version.publish"]))
        db.commit()

    def snapshot():
        with Session(engine) as db:
            return {
                "roles": {
                    r.code: (
                        r.id,
                        r.name,
                        r.data_scope,
                        r.enabled,
                        r.is_system,
                        r.revision,
                        r.created_at,
                        r.created_by,
                        r.updated_at,
                        r.updated_by,
                    )
                    for r in db.scalars(select(Role))
                },
                "links": set(
                    db.execute(select(RolePermission.role_id, RolePermission.permission_id)).all()
                ),
                "users": list(db.execute(select(User.__table__).order_by(User.id)).all()),
                "assignments": list(
                    db.execute(
                        select(UserRole.__table__).order_by(UserRole.user_id, UserRole.role_id)
                    ).all()
                ),
                "versions": list(db.execute(select(Version.__table__).order_by(Version.id)).all()),
                "permissions": list(
                    db.execute(select(Permission.__table__).order_by(Permission.id)).all()
                ),
                "audits": list(db.scalars(select(OperationLog.id).order_by(OperationLog.id))),
            }

    if mysql and case == "normal":
        from app.core.mysql_preflight import validate_mysql

        with engine.connect() as connection:
            validate_mysql(connection, allow_legacy=True)
            with pytest.raises(RuntimeError, match="Alembic head"):
                validate_mysql(connection)

    before = snapshot()
    if case in {"collision", "incomplete", "rollback"}:
        with monkeypatch.context() as patch:
            if case == "rollback":
                original = Connection.execute
                count = 0

                def fail_second_audit(self, statement, *args, **kwargs):
                    nonlocal count
                    if (
                        getattr(statement, "is_insert", False)
                        and statement.table.name == "sys_operation_log"
                    ):
                        count += 1
                        if count == 2:
                            raise RuntimeError("injected migration audit failure")
                    return original(self, statement, *args, **kwargs)

                patch.setattr(Connection, "execute", fail_second_audit)
            match = {
                "collision": "custom role",
                "incomplete": "catalog is incomplete",
                "rollback": "injected migration audit",
            }[case]
            with pytest.raises(RuntimeError, match=match):
                command.upgrade(cfg, "head")
        assert snapshot() == before
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == old
        return

    command.upgrade(cfg, "head")
    after = snapshot()
    if mysql:
        from app.core.mysql_preflight import validate_mysql

        with engine.connect() as connection:
            validate_mysql(connection)
    for key in ("users", "assignments", "versions", "permissions"):
        assert after[key] == before[key], key
    expected_links = set(before["links"])
    for code, row in before["roles"].items():
        if code not in TARGETS:
            assert after["roles"][code] == row
            continue
        current = after["roles"][code]
        assert current[:5] == row[:5] and current[6:8] == row[6:8]
        assert current[5] == row[5] + 1
        expected_links.update((row[0], perms[c]) for c in LEGACY_MISSING[code])
    assert after["links"] == expected_links
    with Session(engine) as db:
        audits = list(
            db.scalars(
                select(OperationLog).where(
                    OperationLog.request_id == "migration-version-role-permissions-v1"
                )
            )
        )
        assert len(audits) == 3
        for log in audits:
            assert log.operator_id is None and log.action == "ROLE_PERMISSION_UPDATE"
            assert log.after_data["revision"] == log.before_data["revision"] + 1
            assert set(log.before_data["permission_ids"]) <= set(log.after_data["permission_ids"])
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == new
    command.upgrade(cfg, "head")
    helper = runpy.run_path(
        str(Path(__file__).parents[1] / "alembic/version_role_permissions_v1.py")
    )
    with engine.begin() as db:
        helper["upgrade_permissions"](db)
    assert snapshot() == after, "Repeated upgrade must not duplicate grants, revisions or audit"

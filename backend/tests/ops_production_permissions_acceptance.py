from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import delete, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from alembic import command
from app.cli.seed import seed_database
from app.models.entities import OperationLog, Permission, Role, RolePermission, UserRole

MERCHANT = {
    "ops.merchant_ad.view": "查看商家广告",
    "ops.merchant_ad.create": "发布商家广告",
    "ops.merchant_ad.edit": "编辑商家广告",
}
MATERIAL = {f"ops.ad_production.{action}" for action in ("view", "create", "edit")}
GRANTS = {
    "SUPER_ADMIN": set(MERCHANT),
    "DESIGNER": {"ops.merchant_ad.view", "ops.merchant_ad.edit"},
    "AD_PRODUCTION_CREATOR": {"ops.merchant_ad.view", "ops.merchant_ad.create"},
    "AD_PRODUCTION_COMPLETER": {"ops.merchant_ad.view", "ops.merchant_ad.edit"},
}
REQUEST_ID = "migration-ops-production-permissions-v1"
DEFAULTS_REQUEST_ID = "migration-ops-role-defaults-v1"
PUBLISH_PERMISSIONS = {
    f"ops.{area}.{action}"
    for area in ("ad_production", "merchant_ad")
    for action in ("view", "create")
}
NEW_DEFAULTS = {
    "CUSTOMER_SERVICE_OPERATIONS": PUBLISH_PERMISSIONS,
    "DESIGNER": {"ops.ad_production.create", "ops.merchant_ad.create"},
}


def _default_revisions(engine):
    if engine.dialect.name == "mysql":
        file, previous, head = "alembic-mysql.ini", "mysql57_0026", "mysql57_0027"
    else:
        file, previous, head = (
            "alembic.ini",
            "0028_ops_production_permissions",
            "0029_ops_role_defaults",
        )
    return Config(str(Path(__file__).resolve().parents[1] / file)), previous, head


def seed_collaboration_fixture(db, *, username, password, fresh):
    config, previous, head = _default_revisions(db.get_bind())
    command.upgrade(config, head if fresh else previous)
    seed_database(db, username=username, password=password)
    if fresh:
        return
    # Historical downgrade tests need a database upgraded from before these grants existed.
    for code, permissions in NEW_DEFAULTS.items():
        db.execute(
            delete(RolePermission).where(
                RolePermission.role_id
                == select(Role.id).where(Role.code == code).scalar_subquery(),
                RolePermission.permission_id.in_(
                    select(Permission.id).where(Permission.code.in_(permissions))
                ),
            )
        )
    db.commit()
    command.upgrade(config, head)


def _revisions(engine):
    if engine.dialect.name == "mysql":
        file, previous, head = "alembic-mysql.ini", "mysql57_0025", "mysql57_0026"
    else:
        file, previous, head = (
            "alembic.ini",
            "0027_ad_production_kinds",
            "0028_ops_production_permissions",
        )
    return Config(str(Path(__file__).resolve().parents[1] / file)), previous, head


def _catalog(db):
    query = select(Permission).where(Permission.code.in_(MATERIAL | MERCHANT.keys()))
    return {permission.code: (permission.id, permission.name) for permission in db.scalars(query)}


def _roles(db):
    states = {}
    for role in db.scalars(select(Role)):
        ids = set(
            db.scalars(
                select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
            )
        )
        states[role.code] = (role.id, role.name, role.data_scope, role.enabled, role.revision, ids)
    return states


def _audits(db, *, downgrade=False, request_id=REQUEST_ID):
    if downgrade:
        request_id += "-downgrade"
    return {
        log.id: log
        for log in db.scalars(select(OperationLog).where(OperationLog.request_id == request_id))
    }


def exercise_ops_production_permission_migration(api):
    _, engine, admin_id, _ = api
    config, previous, head = _revisions(engine)
    command.downgrade(config, previous)
    with Session(engine) as db:
        # Recreate the existing database before the catalog split from the seeded test fixture.
        db.execute(delete(Permission).where(Permission.code.in_(MERCHANT)))
        material_view, old_name = _catalog(db)["ops.ad_production.view"]
        assert old_name == "查看制作需求"
        material_edit = db.scalar(
            select(Permission).where(Permission.code == "ops.ad_production.edit")
        )
        material_edit.name = "编辑制作需求 "
        custom = Role(code="OPS_CUSTOM", name="旧物料角色", is_system=False)
        db.add(custom)
        db.flush()
        custom_id = custom.id
        db.add_all(
            [
                RolePermission(role_id=custom_id, permission_id=material_view),
                UserRole(user_id=admin_id, role_id=custom_id),
            ]
        )
        db.commit()
        baseline = _roles(db)
        old_catalog = _catalog(db)
        old_audits = set(_audits(db))

    command.upgrade(config, head)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
        after = _roles(db)
        catalog = _catalog(db)
        assert {code: catalog[code][1] for code in MERCHANT} == MERCHANT
        assert catalog["ops.ad_production.view"] == (material_view, "查看物料制作")
        assert catalog["ops.ad_production.edit"] == old_catalog["ops.ad_production.edit"]
        assert all(catalog[code][0] == old_catalog[code][0] for code in MATERIAL)
        assert db.get(UserRole, (admin_id, custom_id)) is not None
        audits = {row.entity_id: row for key, row in _audits(db).items() if key not in old_audits}
        assert set(audits) == {after[code][0] for code in GRANTS}
        for code, state in baseline.items():
            if code not in GRANTS:
                assert after[code] == state
                continue
            role_id, name, scope, enabled, revision, before_ids = state
            ids = before_ids | {catalog[permission][0] for permission in GRANTS[code]}
            assert after[code] == (role_id, name, scope, enabled, revision + 1, ids)
            audit = audits[role_id]
            assert audit.operator_id is None and audit.action == "ROLE_PERMISSION_UPDATE"
            assert audit.before_data == {"permission_ids": sorted(before_ids), "revision": revision}
            assert audit.after_data == {"permission_ids": sorted(ids), "revision": revision + 1}
        old_downgrade_ids = set(_audits(db, downgrade=True))

    command.downgrade(config, previous)
    with Session(engine) as db:
        assert _catalog(db)["ops.ad_production.view"] == (material_view, "查看制作需求")
        assert _catalog(db)["ops.ad_production.edit"] == old_catalog["ops.ad_production.edit"]
        assert db.get(UserRole, (admin_id, custom_id)) is not None
        rolled_back = _roles(db)
        for code in baseline:
            assert rolled_back[code][-1] == baseline[code][-1]
        downgrade_audits = _audits(db, downgrade=True)
        assert len(set(downgrade_audits) - old_downgrade_ids) == len(GRANTS)

    command.upgrade(config, head)
    with Session(engine) as db:
        assert _catalog(db) == catalog
        replayed = _roles(db)
        for code in baseline:
            assert replayed[code][-1] == after[code][-1]
            assert replayed[code][-2] == after[code][-2] + (2 if code in GRANTS else 0)
        assert set(_audits(db, downgrade=True)) == set(downgrade_audits)


def exercise_ops_production_permission_guards(api):
    _, engine, _, _ = api
    config, previous, head = _revisions(engine)
    command.downgrade(config, previous)
    view_code = "ops.merchant_ad.view"
    with Session(engine) as db:
        view = db.scalar(select(Permission).where(Permission.code == view_code))
        view_id = view.id
        view.name = "Existing reserved-code collision"
        designer = db.scalar(select(Role).where(Role.code == "DESIGNER"))
        designer.enabled = False
        creator = db.scalar(select(Role).where(Role.code == "AD_PRODUCTION_CREATOR"))
        creator.is_system = False
        db.commit()
        baseline = _roles(db)

    with pytest.raises(RuntimeError, match="conflicts with the catalog"):
        command.upgrade(config, head)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == previous
        assert _roles(db) == baseline
        db.get(Permission, view_id).name = MERCHANT[view_code]
        creator_id = baseline["AD_PRODUCTION_CREATOR"][0]
        db.add(RolePermission(role_id=creator_id, permission_id=view_id))
        db.commit()

    with pytest.raises(RuntimeError, match="unexpected grant"):
        command.upgrade(config, head)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == previous
        db.delete(db.get(RolePermission, (creator_id, view_id)))
        db.commit()

    command.upgrade(config, head)
    with Session(engine) as db:
        after = _roles(db)
        for code in ("AD_PRODUCTION_CREATOR", "DESIGNER"):
            assert after[code] == baseline[code]
        db.add(RolePermission(role_id=creator_id, permission_id=view_id))
        db.commit()

    with pytest.raises(RuntimeError, match="production permission downgrade refused"):
        command.downgrade(config, previous)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
        assert db.get(RolePermission, (creator_id, view_id)) is not None


def exercise_ops_default_migration(api, monkeypatch):
    _, engine, admin_id, _ = api
    config, previous, head = _default_revisions(engine)
    command.downgrade(config, previous)
    with Session(engine) as db:
        permissions = {code: pid for code, (pid, _) in _catalog(db).items()}
        support = db.scalar(select(Role).where(Role.code == "CUSTOMER_SERVICE_OPERATIONS"))
        support.name = "现场运营"
        support.data_scope = "TEAM"
        db.add_all(
            RolePermission(role_id=support.id, permission_id=permissions[code])
            for code in ("ops.ad_production.view", "ops.ad_production.edit")
        )
        designer_id = db.scalar(select(Role.id).where(Role.code == "DESIGNER"))
        db.delete(db.get(RolePermission, (designer_id, permissions["ops.merchant_ad.edit"])))
        custom = Role(code="OPS_LOCAL", name="本地自定义", data_scope="TEAM", is_system=False)
        db.add(custom)
        db.flush()
        db.add(RolePermission(role_id=custom.id, permission_id=permissions["ops.merchant_ad.edit"]))
        baseline_roles = _roles(db)
        related_ids = [
            baseline_roles[code][0]
            for code in ("AD_PRODUCTION_CREATOR", "AD_PRODUCTION_COMPLETER", "OPS_LOCAL")
        ]
        db.add_all(UserRole(user_id=admin_id, role_id=role_id) for role_id in related_ids)
        db.commit()
        baseline_roles = _roles(db)
        baseline_audits = set(_audits(db, request_id=DEFAULTS_REQUEST_ID))
    if engine.dialect.name == "mysql":
        from app.core.mysql_preflight import validate_mysql

        with engine.connect() as connection:
            assert validate_mysql(connection, allow_legacy=True)["table_count"] == 38
            with pytest.raises(RuntimeError, match="Alembic head"):
                validate_mysql(connection)

    original_execute = Connection.execute
    audit_attempts = 0

    def fail_second_audit(connection, statement, *args, **kwargs):
        nonlocal audit_attempts
        if getattr(statement, "is_insert", False) and statement.table.name == "sys_operation_log":
            audit_attempts += 1
            if audit_attempts == 2:
                raise RuntimeError("injected preset grant audit failure")
        return original_execute(connection, statement, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Connection, "execute", fail_second_audit)
        with pytest.raises(RuntimeError, match="injected preset grant audit failure"):
            command.upgrade(config, head)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == previous
        assert _roles(db) == baseline_roles
        assert set(_audits(db, request_id=DEFAULTS_REQUEST_ID)) == baseline_audits

    command.upgrade(config, head)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
        after = _roles(db)
        audit_rows = {
            row.entity_id: row
            for key, row in _audits(db, request_id=DEFAULTS_REQUEST_ID).items()
            if key not in baseline_audits
        }
        assert set(audit_rows) == {baseline_roles[code][0] for code in NEW_DEFAULTS}
        for code, state in baseline_roles.items():
            if code not in NEW_DEFAULTS:
                assert after[code] == state
                continue
            role_id, name, scope, enabled, revision, before_ids = state
            grants = PUBLISH_PERMISSIONS if code == "CUSTOMER_SERVICE_OPERATIONS" else permissions
            after_ids = before_ids | {permissions[grant] for grant in grants}
            assert after[code] == (role_id, name, scope, enabled, revision + 1, after_ids)
            audit = audit_rows[role_id]
            assert audit.action == "ROLE_PERMISSION_UPDATE" and audit.operator_id is None
            assert audit.before_data == {"permission_ids": sorted(before_ids), "revision": revision}
            assert audit.after_data == {
                "permission_ids": sorted(after_ids),
                "revision": revision + 1,
            }
        assert all(db.get(UserRole, (admin_id, role_id)) for role_id in related_ids)
        replay_audit_ids = set(_audits(db, request_id=DEFAULTS_REQUEST_ID))
        baseline_rollbacks = set(_audits(db, downgrade=True, request_id=DEFAULTS_REQUEST_ID))

    command.upgrade(config, head)
    with Session(engine) as db:
        assert _roles(db) == after
        assert set(_audits(db, request_id=DEFAULTS_REQUEST_ID)) == replay_audit_ids
        designer_id = after["DESIGNER"][0]
        independent_grant = db.scalar(
            select(Permission.id).where(Permission.code == "rd.feedback.view")
        )
        db.add(RolePermission(role_id=designer_id, permission_id=independent_grant))
        db.commit()

    command.downgrade(config, previous)
    with Session(engine) as db:
        restored = _roles(db)
        for code, state in baseline_roles.items():
            assert restored[code][:4] == state[:4]
            expected = state[-1] | ({independent_grant} if code == "DESIGNER" else set())
            assert restored[code][-1] == expected
        assert all(db.get(UserRole, (admin_id, role_id)) for role_id in related_ids)
        assert set(_audits(db, request_id=DEFAULTS_REQUEST_ID)) == replay_audit_ids
        current_rollbacks = _audits(db, downgrade=True, request_id=DEFAULTS_REQUEST_ID)
        assert len(set(current_rollbacks) - baseline_rollbacks) == len(NEW_DEFAULTS)


def exercise_ops_default_guards(api):
    _, engine, _, _ = api
    config, previous, head = _default_revisions(engine)
    command.downgrade(config, previous)
    with Session(engine) as db:
        support = db.scalar(select(Role).where(Role.code == "CUSTOMER_SERVICE_OPERATIONS"))
        support.is_system = False
        designer = db.scalar(select(Role).where(Role.code == "DESIGNER"))
        designer.enabled = False
        designer_id = designer.id
        db.commit()
        baseline = _roles(db)
        original_audits = set(_audits(db, request_id=DEFAULTS_REQUEST_ID))

    command.upgrade(config, head)
    with Session(engine) as db:
        assert _roles(db) == baseline
        assert set(_audits(db, request_id=DEFAULTS_REQUEST_ID)) == original_audits

    command.downgrade(config, previous)
    with Session(engine) as db:
        db.execute(delete(RolePermission).where(RolePermission.role_id == designer_id))
        db.delete(db.get(Role, designer_id))
        db.commit()

    command.upgrade(config, head)
    with Session(engine) as db:
        assert _roles(db) == {code: state for code, state in baseline.items() if code != "DESIGNER"}
        assert set(_audits(db, request_id=DEFAULTS_REQUEST_ID)) == original_audits


def exercise_ops_defaults_fresh_seed(api):
    _, engine, _, _ = api
    config, previous, head = _default_revisions(engine)
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
        permissions = {code: pid for code, (pid, _) in _catalog(db).items()}
        roles = _roles(db)
        ops_ids = set(permissions.values())
        support = roles["CUSTOMER_SERVICE_OPERATIONS"]
        designer = roles["DESIGNER"]
        assert support[2] == "ALL" and support[-1] & ops_ids == {
            permissions[code] for code in PUBLISH_PERMISSIONS
        }
        assert designer[2] == "SELF" and designer[-1] & ops_ids == ops_ids

    command.downgrade(config, previous)
    with Session(engine) as db:
        assert _roles(db)["CUSTOMER_SERVICE_OPERATIONS"] == support

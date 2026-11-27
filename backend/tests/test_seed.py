from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.cli import seed
from app.models.entities import Permission, Role, RolePermission, User, UserRole
from app.models.enums import DataScope

V15_FIXED_ROLE_CODES = {
    "MEMBER",
    "CUSTOMER_SERVICE_OPERATIONS",
    "PRODUCT_MANAGER",
    "DEVELOPMENT_LEAD",
    "TESTER",
    "SUPER_ADMIN",
}

# Frozen V1.5 default data-scope per base role.
EXPECTED_ROLE_SCOPES = {
    "MEMBER": DataScope.SELF,
    "CUSTOMER_SERVICE_OPERATIONS": DataScope.ALL,
    "PRODUCT_MANAGER": DataScope.ALL,
    "DEVELOPMENT_LEAD": DataScope.SELF,
    "TESTER": DataScope.SELF,
    "SUPER_ADMIN": DataScope.ALL,
}


@pytest.fixture
def seed_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission):
        counter = iter(range(1, 1000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        for model, listener in listeners:
            event.remove(model, "before_insert", listener)
        engine.dispose()


def _count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_creates_v15_roles_permissions_and_is_idempotent(
    seed_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(seed, "hash_password", lambda _password: "hashed-initial-password")

    seed.seed_database(seed_session, username="admin", password="initial-password")
    first_counts = {
        model: _count(seed_session, model)
        for model in (User, Role, Permission, UserRole, RolePermission)
    }
    seed.seed_database(seed_session, username="admin", password="different-password")

    assert _count(seed_session, User) == 1
    assert _count(seed_session, Role) == len(seed.BASE_ROLES)
    assert _count(seed_session, Permission) == len(seed.PERMISSIONS)
    assert {
        model: _count(seed_session, model)
        for model in (User, Role, Permission, UserRole, RolePermission)
    } == first_counts

    roles = {role.code: role for role in seed_session.scalars(select(Role)).all()}
    assert V15_FIXED_ROLE_CODES.issubset(roles)
    assert {"AD_PRODUCTION_CREATOR", "AD_PRODUCTION_COMPLETER"}.isdisjoint(roles)
    permissions = {
        permission.code: permission for permission in seed_session.scalars(select(Permission))
    }
    assert {
        code: permission.name
        for code, permission in permissions.items()
        if code.startswith(("ops.ad_production.", "ops.merchant_ad."))
    } == {
        "ops.ad_production.view": "查看物料制作",
        "ops.ad_production.create": "发布物料制作",
        "ops.ad_production.edit": "编辑物料制作",
        "ops.merchant_ad.view": "查看商家广告",
        "ops.merchant_ad.create": "发布商家广告",
        "ops.merchant_ad.edit": "编辑商家广告",
    }
    ops_permissions = {
        permission.id: code
        for code, permission in permissions.items()
        if code.startswith(("ops.ad_production.", "ops.merchant_ad."))
    }
    expected_ops_grants = {
        "CUSTOMER_SERVICE_OPERATIONS": {
            "ops.ad_production.view",
            "ops.ad_production.create",
            "ops.merchant_ad.view",
            "ops.merchant_ad.create",
        },
        "DESIGNER": set(ops_permissions.values()),
        "SUPER_ADMIN": set(ops_permissions.values()),
    }
    for code, role in roles.items():
        grants = seed_session.scalars(
            select(RolePermission.permission_id).where(RolePermission.role_id == role.id)
        )
        assert {
            ops_permissions[permission_id]
            for permission_id in grants
            if permission_id in ops_permissions
        } == expected_ops_grants.get(code, set())
    # Frozen V1.5 data-scope matrix. Customer-service and product owners process
    # the shared feedback pool and therefore hold ALL scope; the rest stay SELF.
    for code, expected_scope in EXPECTED_ROLE_SCOPES.items():
        assert roles[code].data_scope is expected_scope, code
        assert roles[code].is_system is True, code
        assert seed.BASE_ROLES[code].data_scope is expected_scope, code
    customer_service = seed.BASE_ROLES["CUSTOMER_SERVICE_OPERATIONS"]
    assert customer_service.name == "客服/运营"
    assert customer_service.data_scope is DataScope.ALL
    assert (
        customer_service.permissions
        == {
            "dashboard.view",
            "rd.feedback.view",
            "rd.feedback.create",
            "rd.feedback.edit",
            "rd.requirement.view",
            "rd.version.view",
            "rd.release.view",
        }
        | expected_ops_grants["CUSTOMER_SERVICE_OPERATIONS"]
    )
    assert "rd.feedback.convert" not in customer_service.permissions
    assert roles["DESIGNER"].data_scope is DataScope.SELF

    admin = seed_session.scalar(select(User).where(User.username == "admin"))
    assert admin is not None
    assert admin.password_hash == "hashed-initial-password"
    assert admin.must_change_password is True
    assert seed_session.get(UserRole, (admin.id, roles["SUPER_ADMIN"].id)) is not None

    super_admin_permission_count = seed_session.scalar(
        select(func.count())
        .select_from(RolePermission)
        .where(RolePermission.role_id == roles["SUPER_ADMIN"].id)
    )
    assert super_admin_permission_count == len(seed.PERMISSIONS)

    designer = roles["DESIGNER"]
    designer.name = "现场设计"
    designer.data_scope = DataScope.TEAM
    permissions["ops.ad_production.edit"].name = "现场进度维护"
    seed_session.commit()
    seed.seed_database(seed_session, username="admin", password=None)
    assert designer.name == "现场设计" and designer.data_scope is DataScope.TEAM
    assert permissions["ops.ad_production.edit"].name == "现场进度维护"


def test_seed_repairs_existing_admin_role_and_missing_links(
    seed_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(seed, "hash_password", lambda _password: "must-not-replace-existing")
    admin = User(
        username="existing-admin",
        display_name="已有管理员",
        password_hash="existing-password-hash",
    )
    super_admin = Role(
        code="SUPER_ADMIN",
        name="待修复管理员",
        data_scope=DataScope.SELF,
        enabled=False,
    )
    seed_session.add_all([admin, super_admin])
    seed_session.commit()

    seed.seed_database(seed_session, username="existing-admin", password=None)
    seed.seed_database(seed_session, username="existing-admin", password=None)

    assert admin.password_hash == "existing-password-hash"
    assert super_admin.name == "超级管理员"
    assert super_admin.data_scope is DataScope.ALL
    assert super_admin.enabled is True
    assert super_admin.is_system is True
    assert seed_session.get(UserRole, (admin.id, super_admin.id)) is not None
    permission_ids = set(
        seed_session.scalars(
            select(RolePermission.permission_id).where(RolePermission.role_id == super_admin.id)
        ).all()
    )
    assert len(permission_ids) == len(seed.PERMISSIONS)
    assert _count(seed_session, UserRole) == 1


def test_seed_refuses_missing_or_short_bootstrap_password(seed_session: Session) -> None:
    with pytest.raises(ValueError, match="8-128"):
        seed.seed_database(seed_session, username="fresh-admin", password=None)
    with pytest.raises(ValueError, match="8-128"):
        seed.seed_database(seed_session, username="fresh-admin", password="short")
    assert _count(seed_session, User) == 0


def test_seed_preserves_legacy_roles_grants_and_assignments(seed_session: Session) -> None:
    admin = User(username="admin", display_name="现有账号", password_hash="existing-password-hash")
    creator = Role(
        code="AD_PRODUCTION_CREATOR",
        name="现场发布人",
        data_scope=DataScope.TEAM,
        is_system=True,
        enabled=False,
        revision=5,
    )
    completer = Role(code="AD_PRODUCTION_COMPLETER", name="既有自定义角色", is_system=False)
    permission = Permission(code="ops.ad_production.view", name="查看物料制作")
    seed_session.add_all([admin, creator, completer, permission])
    seed_session.flush()
    seed_session.add_all(
        [
            RolePermission(role_id=creator.id, permission_id=permission.id),
            UserRole(user_id=admin.id, role_id=creator.id),
            UserRole(user_id=admin.id, role_id=completer.id),
        ]
    )
    seed_session.commit()

    seed.seed_database(seed_session, username="admin", password=None)

    assert creator.name == "现场发布人" and creator.data_scope is DataScope.TEAM
    assert creator.is_system and not creator.enabled and creator.revision == 5
    assert completer.name == "既有自定义角色" and not completer.is_system
    assert all(seed_session.get(UserRole, (admin.id, role.id)) for role in (creator, completer))
    links = select(RolePermission.permission_id)
    assert set(seed_session.scalars(links.where(RolePermission.role_id == creator.id))) == {
        permission.id
    }
    assert not set(seed_session.scalars(links.where(RolePermission.role_id == completer.id)))


def test_seed_preserves_ineligible_ops_presets(
    seed_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(seed, "hash_password", lambda _password: "hashed-initial-password")
    custom = Role(code="CUSTOMER_SERVICE_OPERATIONS", name="客服自定义", is_system=False)
    disabled = Role(code="DESIGNER", name="停用设计", is_system=True, enabled=False)
    seed_session.add_all([custom, disabled])
    seed_session.commit()

    seed.seed_database(seed_session, username="admin", password="initial-password")

    assert custom.name == "客服自定义" and not custom.is_system and custom.enabled
    assert disabled.name == "停用设计" and disabled.is_system and not disabled.enabled
    assert not seed_session.scalar(
        select(RolePermission.permission_id).where(
            RolePermission.role_id.in_((custom.id, disabled.id))
        )
    )

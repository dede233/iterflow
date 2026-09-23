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
    # Frozen V1.5 data-scope matrix. Customer-service and product owners process
    # the shared feedback pool and therefore hold ALL scope; the rest stay SELF.
    for code, expected_scope in EXPECTED_ROLE_SCOPES.items():
        assert roles[code].data_scope is expected_scope, code
        assert roles[code].is_system is True, code
        assert seed.BASE_ROLES[code].data_scope is expected_scope, code
    customer_service = seed.BASE_ROLES["CUSTOMER_SERVICE_OPERATIONS"]
    assert customer_service.name == "客服/运营"
    assert customer_service.data_scope is DataScope.ALL
    assert customer_service.permissions == {
        "dashboard.view",
        "rd.feedback.view",
        "rd.feedback.create",
        "rd.feedback.edit",
        "rd.requirement.view",
        "rd.version.view",
        "rd.release.view",
    }
    assert "rd.feedback.convert" not in customer_service.permissions

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

    seed.seed_database(seed_session, username="existing-admin", password="ignored-password")
    seed.seed_database(seed_session, username="existing-admin", password="ignored-password")

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

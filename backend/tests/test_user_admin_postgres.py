import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.audit_context import AuditContext, audit_context
from app.core.database import Base
from app.core.exceptions import ConflictError
from app.models.entities import OperationLog, Role, User, UserRole
from app.models.enums import DataScope, UserStatus
from app.schemas.user import UserRoleUpdate
from app.services.user_administration_service import UserAdministrationService

POSTGRES_URL = os.getenv("ITERFLOW_TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="set ITERFLOW_TEST_POSTGRES_URL to run PostgreSQL row-lock verification",
)
def test_concurrent_super_admin_removal_preserves_one_effective_admin():
    """Two real PostgreSQL sessions cannot remove both active SUPER_ADMIN users."""
    assert POSTGRES_URL is not None
    schema = f"phase723_{uuid4().hex}"
    administration_engine = create_engine(POSTGRES_URL)
    with administration_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        POSTGRES_URL,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=4,
    )
    tables = [User.__table__, Role.__table__, UserRole.__table__, OperationLog.__table__]
    try:
        Base.metadata.create_all(engine, tables=tables)
        with Session(engine) as session:
            super_admin_role = Role(
                code="SUPER_ADMIN",
                name="Super Administrator",
                data_scope=DataScope.ALL,
                enabled=True,
                is_system=True,
            )
            first = User(
                username="first-super-admin",
                display_name="First Super Admin",
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            second = User(
                username="second-super-admin",
                display_name="Second Super Admin",
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            session.add_all([super_admin_role, first, second])
            session.flush()
            session.add_all(
                [
                    UserRole(user_id=first.id, role_id=super_admin_role.id),
                    UserRole(user_id=second.id, role_id=super_admin_role.id),
                ]
            )
            super_admin_role_id = super_admin_role.id
            user_ids = (first.id, second.id)
            session.commit()

        barrier = Barrier(2)

        def remove_own_super_admin(user_id: int) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    with audit_context(AuditContext(operator_id=user_id)):
                        UserAdministrationService(session).update_roles(
                            user_id,
                            UserRoleUpdate(role_ids=[], revision=1),
                            user_id,
                        )
                except ConflictError as exc:
                    session.rollback()
                    assert exc.message == "至少必须保留一个有效的超级管理员"
                    return "conflict"
                return "success"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(remove_own_super_admin, user_ids))

        assert sorted(outcomes) == ["conflict", "success"]
        with Session(engine) as session:
            effective_count = session.scalar(
                select(func.count(User.id))
                .join(UserRole, UserRole.user_id == User.id)
                .where(
                    User.status == UserStatus.ACTIVE,
                    UserRole.role_id == super_admin_role_id,
                )
            )
            revisions = sorted(session.scalars(select(User.revision).order_by(User.id)).all())
            audit_count = session.scalar(
                select(func.count(OperationLog.id)).where(OperationLog.action == "ROLES_UPDATE")
            )
            assert effective_count == 1
            assert revisions == [1, 2]
            assert audit_count == 1
    finally:
        engine.dispose()
        with administration_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        administration_engine.dispose()

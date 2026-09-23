import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    OperationLog,
    Requirement,
    User,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    DataScope,
    Priority,
    RequirementSource,
    RequirementStatus,
    UserStatus,
    VersionStatus,
)
from app.schemas.version import MoveRequirementRequest
from app.services.version_service import VersionService

POSTGRES_URL = os.getenv("ITERFLOW_TEST_POSTGRES_URL")
POSTGRES_TABLES = [
    User.__table__,
    BusinessSystem.__table__,
    BusinessModule.__table__,
    OperationLog.__table__,
    Version.__table__,
    Requirement.__table__,
    VersionRequirement.__table__,
]


@pytest.fixture
def postgres_engine():
    if not POSTGRES_URL:
        pytest.skip("set ITERFLOW_TEST_POSTGRES_URL to run PostgreSQL relation-lock verification")
    from sqlalchemy import create_engine

    schema = f"phase81_version_{uuid4().hex}"
    admin_engine = create_engine(POSTGRES_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        POSTGRES_URL,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=6,
    )
    try:
        Base.metadata.create_all(engine, tables=POSTGRES_TABLES)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_relation(engine, *, hidden_source: bool = False) -> dict[str, int]:
    with Session(engine) as session:
        owner = User(
            username=f"owner-{uuid4().hex[:8]}",
            display_name="Owner",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        other = User(
            username=f"other-{uuid4().hex[:8]}",
            display_name="Other",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        session.add_all([owner, other])
        session.flush()
        source = Version(
            version_no=f"VS-{uuid4().hex[:8]}",
            name="source",
            status=VersionStatus.PLANNING,
            owner_id=owner.id,
            created_by=owner.id,
        )
        target_a = Version(
            version_no=f"VA-{uuid4().hex[:8]}",
            name="target-a",
            status=VersionStatus.PLANNING,
            owner_id=owner.id,
            created_by=owner.id,
        )
        target_b = Version(
            version_no=f"VB-{uuid4().hex[:8]}",
            name="target-b",
            status=VersionStatus.PLANNING,
            owner_id=other.id if hidden_source else owner.id,
            created_by=other.id if hidden_source else owner.id,
        )
        session.add_all([source, target_a, target_b])
        session.flush()
        requirement = Requirement(
            requirement_no=f"REQ-{uuid4().hex[:8]}",
            title="concurrent relation",
            requirement_type="FEATURE",
            source=RequirementSource.DIRECT,
            priority=Priority.P2,
            status=RequirementStatus.PLANNED,
            description="relation race test",
            owner_id=owner.id,
            current_version_id=source.id,
            created_by=owner.id,
        )
        session.add(requirement)
        session.flush()
        relation = VersionRequirement(
            version_id=source.id,
            requirement_id=requirement.id,
            added_by=owner.id,
            active=True,
        )
        session.add(relation)
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "source_id": source.id,
            "target_a_id": target_a.id,
            "target_b_id": target_b.id,
            "requirement_id": requirement.id,
        }


def test_concurrent_moves_use_revision_cas_and_keep_single_active_relation(postgres_engine):
    ids = _seed_relation(postgres_engine)
    barrier = Barrier(2)

    def move(target_id: int) -> str:
        with Session(postgres_engine, expire_on_commit=False) as session:
            barrier.wait(timeout=10)
            try:
                VersionService(session).move_requirement(
                    target_id,
                    MoveRequirementRequest(
                        requirement_id=ids["requirement_id"],
                        revision=1,
                        version_revision=1,
                        reason="parallel move",
                    ),
                    ids["owner_id"],
                    viewer_scope=DataScope.ALL,
                    viewer_id=ids["owner_id"],
                )
            except ConflictError:
                session.rollback()
                return "conflict"
            return "success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(move, (ids["target_a_id"], ids["target_b_id"])))
    assert sorted(outcomes) == ["conflict", "success"]

    with Session(postgres_engine) as session:
        requirement = session.get(Requirement, ids["requirement_id"])
        assert requirement is not None
        assert requirement.revision == 2
        assert requirement.current_version_id in {ids["target_a_id"], ids["target_b_id"]}
        active_relations = session.scalars(
            select(VersionRequirement).where(
                VersionRequirement.requirement_id == ids["requirement_id"],
                VersionRequirement.active.is_(True),
            )
        ).all()
        assert len(active_relations) == 1
        assert active_relations[0].version_id == requirement.current_version_id


def test_move_revalidates_scope_after_concurrent_source_relation_change(
    postgres_engine, monkeypatch: pytest.MonkeyPatch
):
    ids = _seed_relation(postgres_engine, hidden_source=True)
    original_lock_versions = VersionService._lock_versions
    interleaved = False

    def lock_with_concurrent_move(service: VersionService, version_ids: set[int]):
        nonlocal interleaved
        if not interleaved:
            interleaved = True
            monkeypatch.setattr(VersionService, "_lock_versions", original_lock_versions)
            with Session(postgres_engine, expire_on_commit=False) as concurrent_session:
                requirement = concurrent_session.get(Requirement, ids["requirement_id"])
                target = concurrent_session.get(Version, ids["target_b_id"])
                assert requirement is not None and target is not None
                VersionService(concurrent_session).move_requirement(
                    ids["target_b_id"],
                    MoveRequirementRequest(
                        requirement_id=requirement.id,
                        revision=requirement.revision,
                        version_revision=target.revision,
                        reason="concurrent source change",
                    ),
                    ids["other_id"],
                    viewer_scope=DataScope.ALL,
                    viewer_id=ids["other_id"],
                )
            monkeypatch.setattr(VersionService, "_lock_versions", lock_with_concurrent_move)
        return original_lock_versions(service, version_ids)

    monkeypatch.setattr(VersionService, "_lock_versions", lock_with_concurrent_move)
    with Session(postgres_engine, expire_on_commit=False) as session:
        requirement = session.get(Requirement, ids["requirement_id"])
        target = session.get(Version, ids["target_a_id"])
        assert requirement is not None and target is not None
        with pytest.raises(NotFoundError):
            VersionService(session).move_requirement(
                ids["target_a_id"],
                MoveRequirementRequest(
                    requirement_id=requirement.id,
                    revision=requirement.revision,
                    version_revision=target.revision,
                    reason="stale-scope move",
                ),
                ids["owner_id"],
                viewer_scope=DataScope.SELF,
                viewer_id=ids["owner_id"],
            )
        session.rollback()

    with Session(postgres_engine) as session:
        requirement = session.get(Requirement, ids["requirement_id"])
        assert requirement is not None
        assert requirement.current_version_id == ids["target_b_id"]
        assert requirement.revision == 2
        active = session.scalars(
            select(VersionRequirement).where(
                VersionRequirement.requirement_id == ids["requirement_id"],
                VersionRequirement.active.is_(True),
            )
        ).all()
        assert len(active) == 1
        assert active[0].version_id == ids["target_b_id"]
        assert (
            session.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "VERSION_REQUIREMENT_MOVE"
                )
            )
            == 1
        )

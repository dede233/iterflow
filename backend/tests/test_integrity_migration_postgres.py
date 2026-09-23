import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.models.entities import (
    AttachmentRelation,
    Feedback,
    FileObject,
    Release,
    Requirement,
    RequirementFeedback,
    User,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    FeedbackStatus,
    FeedbackType,
    Priority,
    ReleaseResult,
    RequirementSource,
    RequirementStatus,
    StorageDriver,
    UserStatus,
    VersionStatus,
)

POSTGRES_URL = os.getenv("ITERFLOW_TEST_POSTGRES_URL")
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture
def migration_schema() -> Iterator[tuple[object, URL, str]]:
    if not POSTGRES_URL:
        pytest.skip("set ITERFLOW_TEST_POSTGRES_URL to run PostgreSQL migration tests")

    schema = f"phase82_migration_{uuid4().hex}"
    admin_engine = create_engine(POSTGRES_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    scoped_url = make_url(POSTGRES_URL)
    env_keys = {
        "DATABASE_URL": scoped_url.render_as_string(hide_password=False),
        "REDIS_URL": "redis://127.0.0.1:6379/15",
        "JWT_SECRET": "phase82-migration-test-secret-value-over-32-characters",
        "PGOPTIONS": f"-c search_path={schema}",
    }
    previous_values = {key: os.environ.get(key) for key in env_keys}
    for key, value in env_keys.items():
        os.environ[key] = value
    get_settings.cache_clear()

    engine = create_engine(scoped_url)
    try:
        command.upgrade(_alembic_config(), "0003_role_system_flag")
        yield engine, scoped_url, schema
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
        for key, previous in previous_values.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        get_settings.cache_clear()


def _upgrade_head(database_url: URL) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _downgrade_0003(database_url: URL) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    try:
        command.downgrade(_alembic_config(), "0003_role_system_flag")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _seed_valid_relations(session: Session) -> dict[str, int]:
    user = User(
        username=f"integrity-{uuid4().hex[:8]}",
        display_name="Integrity Test",
        password_hash="unused",
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    session.add(user)
    session.flush()
    version_a = Version(
        version_no=f"VA-{uuid4().hex[:8]}",
        name="Version A",
        status=VersionStatus.PLANNING,
        owner_id=user.id,
        created_by=user.id,
    )
    version_b = Version(
        version_no=f"VB-{uuid4().hex[:8]}",
        name="Version B",
        status=VersionStatus.PLANNING,
        owner_id=user.id,
        created_by=user.id,
    )
    requirement = Requirement(
        requirement_no=f"REQ-{uuid4().hex[:8]}",
        title="Integrity requirement",
        requirement_type="FEATURE",
        source=RequirementSource.DIRECT,
        priority=Priority.P2,
        status=RequirementStatus.PLANNED,
        description="Test",
        owner_id=user.id,
        created_by=user.id,
    )
    feedback = Feedback(
        feedback_no=f"FB-{uuid4().hex[:8]}",
        title="Integrity feedback",
        feedback_type=FeedbackType.NEW_FEATURE,
        status=FeedbackStatus.REQUIREMENT_LINKED,
        submitter_id=user.id,
        description="Test",
    )
    session.add_all([version_a, version_b, requirement, feedback])
    session.flush()

    requirement.current_version_id = version_a.id
    session.add(
        VersionRequirement(
            version_id=version_a.id,
            requirement_id=requirement.id,
            active=True,
            added_by=user.id,
        )
    )
    feedback.main_requirement_id = requirement.id
    session.add(
        RequirementFeedback(
            requirement_id=requirement.id,
            feedback_id=feedback.id,
            is_primary=True,
        )
    )
    session.commit()
    return {
        "user_id": user.id,
        "version_a_id": version_a.id,
        "version_b_id": version_b.id,
        "requirement_id": requirement.id,
        "feedback_id": feedback.id,
    }


def _assert_commit_rejected(session: Session, operation: object) -> None:
    try:
        operation()  # type: ignore[operator]
        session.commit()
    except IntegrityError:
        session.rollback()
    else:
        pytest.fail("PostgreSQL accepted a write that violates a Phase 8.2 integrity invariant")


def test_integrity_migration_round_trip_and_database_constraints(migration_schema) -> None:
    engine, scoped_url, _schema = migration_schema
    _upgrade_head(scoped_url)

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0004_integrity"
        )

    with Session(engine) as session:
        ids = _seed_valid_relations(session)

    # A normal transaction that changes both mirror representations is valid.
    with Session(engine) as session:
        requirement = session.get(Requirement, ids["requirement_id"])
        version_requirement = session.scalar(
            select(VersionRequirement).where(
                VersionRequirement.requirement_id == ids["requirement_id"]
            )
        )
        assert requirement is not None and version_requirement is not None
        version_requirement.active = False
        version_requirement.removed_at = requirement.updated_at
        replacement = VersionRequirement(
            version_id=ids["version_b_id"],
            requirement_id=requirement.id,
            active=True,
            added_by=ids["user_id"],
        )
        session.add(replacement)
        requirement.current_version_id = ids["version_b_id"]
        session.commit()

    with Session(engine) as session:
        version = session.get(Version, ids["version_a_id"])
        assert version is not None
        release_values = dict(
            version_id=version.id,
            released_at=version.updated_at,
            result=ReleaseResult.SUCCESS,
            release_notes="release",
            created_by=ids["user_id"],
        )
        session.add(Release(**release_values))
        session.commit()
        session.add(Release(**release_values))
        _assert_commit_rejected(session, lambda: None)

    with Session(engine) as session:
        file = FileObject(
            storage_key=f"uploads/{uuid4().hex}",
            original_name="evidence.txt",
            mime_type="text/plain",
            size=1,
            sha256="0" * 64,
            storage_driver=StorageDriver.LOCAL,
            created_by=ids["user_id"],
        )
        session.add(file)
        session.flush()
        relation = AttachmentRelation(
            file_id=file.id, entity_type="FEEDBACK", entity_id=ids["feedback_id"]
        )
        session.add(relation)
        session.commit()
        session.add(
            AttachmentRelation(
                file_id=file.id, entity_type="FEEDBACK", entity_id=ids["feedback_id"]
            )
        )
        _assert_commit_rejected(session, lambda: None)

    with Session(engine) as session:
        session.add(
            RequirementFeedback(
                requirement_id=ids["requirement_id"],
                feedback_id=ids["feedback_id"],
                is_primary=False,
            )
        )
        _assert_commit_rejected(session, lambda: None)

    with Session(engine) as session:
        requirement = session.get(Requirement, ids["requirement_id"])
        assert requirement is not None
        requirement.current_version_id = ids["version_a_id"]
        _assert_commit_rejected(session, lambda: None)

    with Session(engine) as session:
        feedback = session.get(Feedback, ids["feedback_id"])
        assert feedback is not None
        feedback.main_requirement_id = None
        _assert_commit_rejected(session, lambda: None)

    _downgrade_0003(scoped_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0003_role_system_flag"
        )
    _upgrade_head(scoped_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0004_integrity"
        )


def test_migration_refuses_to_guess_existing_mirror_data(migration_schema) -> None:
    engine, scoped_url, _schema = migration_schema
    with Session(engine) as session:
        user = User(
            username=f"legacy-{uuid4().hex[:8]}",
            display_name="Legacy data",
            password_hash="unused",
            status=UserStatus.ACTIVE,
            must_change_password=False,
        )
        session.add(user)
        session.flush()
        version = Version(
            version_no=f"VL-{uuid4().hex[:8]}",
            name="Legacy version",
            status=VersionStatus.PLANNING,
            owner_id=user.id,
            created_by=user.id,
        )
        requirement = Requirement(
            requirement_no=f"RLEG-{uuid4().hex[:8]}",
            title="Legacy inconsistent requirement",
            requirement_type="FEATURE",
            source=RequirementSource.DIRECT,
            priority=Priority.P2,
            status=RequirementStatus.PLANNED,
            description="Must not be repaired automatically",
            owner_id=user.id,
            current_version_id=None,
            created_by=user.id,
        )
        session.add_all([version, requirement])
        session.flush()
        requirement.current_version_id = version.id
        session.commit()
        requirement_id = requirement.id
        version_id = version.id

    with pytest.raises(RuntimeError, match="current_version_id disagrees"):
        _upgrade_head(scoped_url)

    with Session(engine) as session:
        requirement = session.get(Requirement, requirement_id)
        assert requirement is not None
        assert requirement.current_version_id == version_id
        assert (
            session.scalar(
                select(func.count(VersionRequirement.id)).where(
                    VersionRequirement.requirement_id == requirement_id
                )
            )
            == 0
        )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0003_role_system_flag"
        )

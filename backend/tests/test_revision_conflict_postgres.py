"""Two PostgreSQL sessions must report the committed winner's CAS metadata."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import ConflictError
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    Feedback,
    OperationLog,
    Requirement,
    RequirementParticipant,
    User,
    Version,
)
from app.models.enums import FeedbackType, RequirementSource, UserStatus
from app.schemas.feedback import FeedbackUpdate
from app.schemas.requirement import RequirementUpdate
from app.schemas.version import VersionUpdate
from app.services.feedback_service import FeedbackService
from app.services.requirement_service import RequirementService
from app.services.version_service import VersionService

POSTGRES_URL = os.getenv("ITERFLOW_TEST_POSTGRES_URL")
POSTGRES_TABLES = [
    User.__table__,
    BusinessSystem.__table__,
    BusinessModule.__table__,
    OperationLog.__table__,
    Version.__table__,
    Requirement.__table__,
    RequirementParticipant.__table__,
    Feedback.__table__,
]


@pytest.fixture
def postgres_engine():
    if not POSTGRES_URL:
        pytest.skip("set ITERFLOW_TEST_POSTGRES_URL to run PostgreSQL CAS verification")
    schema = f"phase2_cas_{uuid4().hex}"
    admin_engine = create_engine(POSTGRES_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(POSTGRES_URL, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine, tables=POSTGRES_TABLES)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.mark.parametrize("entity_type", ["feedback", "requirement", "version"])
def test_two_users_read_then_write_stale_revision(postgres_engine, entity_type):
    with Session(postgres_engine) as seed:
        first = User(
            username="first", display_name="A", password_hash="unused", status=UserStatus.ACTIVE
        )
        second = User(
            username="second", display_name="B", password_hash="unused", status=UserStatus.ACTIVE
        )
        seed.add_all([first, second])
        seed.flush()
        entities = {
            "feedback": Feedback(
                feedback_no="FB-1",
                title="original",
                feedback_type=FeedbackType.SYSTEM_ISSUE,
                description="original description",
                submitter_id=first.id,
                created_by=first.id,
                updated_by=first.id,
            ),
            "requirement": Requirement(
                requirement_no="REQ-1",
                title="original",
                requirement_type="FEATURE",
                source=RequirementSource.DIRECT,
                description="original description",
                created_by=first.id,
                updated_by=first.id,
            ),
            "version": Version(
                version_no="V1",
                name="original",
                created_by=first.id,
                updated_by=first.id,
            ),
        }
        item = entities[entity_type]
        seed.add(item)
        seed.commit()
        item_id, first_id, second_id = item.id, first.id, second.id

    model_and_update = {
        "feedback": (Feedback, FeedbackService, FeedbackUpdate, "title"),
        "requirement": (Requirement, RequirementService, RequirementUpdate, "title"),
        "version": (Version, VersionService, VersionUpdate, "name"),
    }
    model, service_type, payload_type, field = model_and_update[entity_type]
    with Session(postgres_engine) as session_a, Session(postgres_engine) as session_b:
        # Both users have read N in separate live transactions before either writes.
        assert session_a.get(model, item_id).revision == 1
        assert session_b.get(model, item_id).revision == 1
        winner = service_type(session_a).update(
            item_id, payload_type(**{field: "saved by A", "revision": 1}), first_id
        )
        assert winner.revision == 2

        with pytest.raises(ConflictError) as raised:
            service_type(session_b).update(
                item_id, payload_type(**{field: "saved by B", "revision": 1}), second_id
            )
        conflict = raised.value
        assert conflict.status_code == 409
        assert conflict.code == 40910
        assert conflict.data["current_revision"] == 2
        assert conflict.data["current_updated_by"] == first_id
        assert conflict.data["current_updated_at"] == winner.updated_at.isoformat()
        session_b.rollback()

    with Session(postgres_engine) as verify:
        stored = verify.get(model, item_id)
        assert getattr(stored, field) == "saved by A"
        assert stored.revision == 2

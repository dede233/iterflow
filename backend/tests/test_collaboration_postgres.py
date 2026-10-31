import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.database import Base, get_db
from app.core.exceptions import ConflictError
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    Permission,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import DataScope
from app.schemas.feedback import FeedbackStatusChange
from app.services.feedback_service import FeedbackService


@pytest.fixture
def collaboration_api():
    url = os.getenv("ITERFLOW_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("isolated PostgreSQL URL required")
    schema = f"workflow_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        all_role = Role(id=1, code="TEAM_ALL", name="全域处理", data_scope=DataScope.ALL)
        self_role = Role(id=2, code="TEAM_SELF", name="本人处理", data_scope=DataScope.SELF)
        db.add_all([all_role, self_role])
        for i in range(1, 5):
            db.add(
                User(
                    id=i,
                    username=f"user{i}",
                    display_name=f"人员{i}",
                    password_hash="unused",
                    must_change_password=False,
                )
            )
        codes = [
            f"rd.{kind}.{action}"
            for kind in ("feedback", "requirement")
            for action in ("view", "create", "edit", "status")
        ]
        for i, code in enumerate(codes, 1):
            db.add(Permission(id=i, code=code, name=code))
        db.flush()
        db.add_all(UserRole(user_id=i, role_id=1 if i < 4 else 2) for i in range(1, 5))
        db.add_all(
            RolePermission(role_id=role, permission_id=i)
            for role in (1, 2)
            for i in range(1, len(codes) + 1)
        )
        db.commit()

    def get_test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    headers = {i: {"Authorization": f"Bearer {create_access_token(i)}"} for i in range(1, 5)}
    try:
        with TestClient(app) as client:
            yield client, headers, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def create_feedback(client, headers, **overrides):
    body = dict(
        title="需要处理的反馈", description="详细内容", feedback_type="OTHER", recipient_ids=[2, 3]
    )
    body.update(overrides)
    return client.post("/api/v1/feedbacks", headers=headers[1], json=body)


def test_recipients_scope_acceptance_and_transfer(collaboration_api):
    client, headers, engine = collaboration_api
    # A SELF user who did not submit this feedback cannot be made a recipient.
    bad = create_feedback(client, headers, recipient_ids=[4])
    assert bad.status_code == 422, bad.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Feedback)) == 0
        assert db.scalar(select(func.count()).select_from(CollaborationEvent)) == 0
    response = create_feedback(client, headers)
    assert response.status_code == 200, response.text
    feedback = response.json()
    base = f"/api/v1/feedbacks/{feedback['id']}"
    assert client.get(base, headers=headers[4]).status_code == 404
    assert (
        client.patch(
            base + "/status", headers=headers[1], json={"status": "ACCEPTED", "revision": 1}
        ).status_code
        == 403
    )
    accepted = client.patch(
        base + "/status", headers=headers[2], json={"status": "ACCEPTED", "revision": 1}
    )
    assert accepted.status_code == 200, accepted.text
    assert (
        client.patch(
            base + "/status", headers=headers[3], json={"status": "ACCEPTED", "revision": 1}
        ).status_code
        == 409
    )
    info = client.get(base + "/collaboration", headers=headers[1]).json()
    assert info["handler_id"] == info["accepted_by"] == 2
    assert info["accepted_at"]
    refused = client.put(
        base + "/recipients", headers=headers[1], json={"revision": 2, "recipient_ids": [3]}
    )
    assert refused.status_code == 409
    assert client.get(base, headers=headers[1]).json()["revision"] == 2
    transferred = client.post(
        base + "/transfer",
        headers=headers[1],
        json={"revision": 2, "handler_id": 3, "reason": "转交跟进"},
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["handler_id"] == 3
    assert transferred.json()["accepted_by"] == 2


def test_participants_grant_only_object_scope_and_preserve_legacy_owner(collaboration_api):
    client, headers, engine = collaboration_api
    req = client.post(
        "/api/v1/requirements",
        headers=headers[1],
        json={"title": "需求内容", "requirement_type": "FEATURE", "description": "说明"},
    ).json()
    base = f"/api/v1/requirements/{req['id']}"
    assert client.get(base, headers=headers[4]).status_code == 404
    response = client.put(
        base + "/participants",
        headers=headers[1],
        json={"revision": 1, "participants": [{"user_id": 4, "role": "DEVELOP"}]},
    )
    assert response.status_code == 200, response.text
    assert client.get(base, headers=headers[4]).status_code == 200
    assert client.get("/api/v1/requirements", headers=headers[4]).json()["total"] == 1
    assert (
        client.put(
            base + "/participants", headers=headers[1], json={"revision": 1, "participants": []}
        ).status_code
        == 409
    )
    assert (
        client.put(
            base + "/participants", headers=headers[1], json={"revision": 2, "participants": []}
        ).status_code
        == 200
    )
    assert client.get(base, headers=headers[4]).status_code == 404
    with Session(engine) as db:
        item = db.get(Requirement, req["id"])
        item.owner_id = (
            4  # Historical owner access remains readable, not an inferred stage assignment.
        )
        db.commit()
    assert client.get(base, headers=headers[4]).status_code == 200


def test_two_receivers_cannot_both_accept(collaboration_api):
    client, headers, engine = collaboration_api
    item = create_feedback(client, headers).json()
    barrier = Barrier(2)

    def accept(uid):
        with Session(engine) as db:
            db.get(Feedback, item["id"])
            barrier.wait(timeout=10)
            try:
                FeedbackService(db).change_status(
                    item["id"],
                    FeedbackStatusChange(status="ACCEPTED", revision=1),
                    uid,
                    DataScope.ALL,
                    uid,
                )
                return "accepted"
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(accept, [2, 3]))
    assert sorted(results) == ["accepted", "conflict"]
    with Session(engine) as db:
        row = db.get(Feedback, item["id"])
        assert row.revision == 2 and row.accepted_by in [2, 3]
        assert (
            db.scalar(
                select(func.count())
                .select_from(CollaborationEvent)
                .where(CollaborationEvent.action == "STATUS_ACCEPTED")
            )
            == 1
        )

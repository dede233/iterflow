from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    Feedback,
    Notification,
    OperationLog,
    Permission,
    Release,
    Requirement,
    RequirementFeedback,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    RequirementStatus,
    UserStatus,
    VersionStatus,
)
from app.schemas.version import PublishVersionRequest
from app.services.version_service import VersionService

SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"

PERMS = {
    "rd.version.view",
    "rd.version.publish",
    "rd.release.view",
    "rd.feedback.view",
    "rd.requirement.view",
}

Fixture = tuple[TestClient, Session, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def pub_api(tmp_path: Path) -> Iterator[Fixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pub.db'}", connect_args={"check_same_thread": False}
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        OperationLog.__table__,
        Feedback.__table__,
        Requirement.__table__,
        Version.__table__,
        VersionRequirement.__table__,
        RequirementFeedback.__table__,
        Release.__table__,
        Notification.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (
        User,
        Role,
        Permission,
        OperationLog,
        Feedback,
        Requirement,
        Version,
        VersionRequirement,
        RequirementFeedback,
        Release,
        Notification,
    ):
        counter = iter(range(1, 100000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        role_all = Role(code="ALLROLE", name="全域", data_scope=DataScope.ALL)
        role_member = Role(code="MEMBERROLE", name="成员", data_scope=DataScope.SELF)
        perms = {code: Permission(code=code, name=code) for code in sorted(PERMS)}
        session.add_all([role_all, role_member, *perms.values()])
        session.flush()
        for perm in perms.values():
            session.add(RolePermission(role_id=role_all.id, permission_id=perm.id))
        # member has only view perms, no publish
        for code in ("rd.version.view", "rd.feedback.view", "rd.requirement.view"):
            session.add(RolePermission(role_id=role_member.id, permission_id=perms[code].id))

        def user(name: str) -> User:
            return User(
                username=name,
                display_name=name,
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )

        boss = user("boss")
        member = user("member")
        session.add_all([boss, member])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=boss.id, role_id=role_all.id),
                UserRole(user_id=member.id, role_id=role_member.id),
            ]
        )
        session.commit()

        ids = {"boss": boss.id, "member": member.id}
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(uid)}"}
            for name, uid in ids.items()
        }
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, session, headers, ids
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def _seed_ready_version(
    session: Session,
    boss_id: int,
    *,
    requirement_status: RequirementStatus = RequirementStatus.DONE,
    version_status: VersionStatus = VersionStatus.READY,
) -> dict[str, int]:
    """A version (default READY) with one requirement and a linked feedback."""
    version = Version(
        version_no="V1.0.0",
        name="首个版本",
        status=version_status,
        created_by=boss_id,
        updated_by=boss_id,
    )
    requirement = Requirement(
        requirement_no="REQ-1",
        title="需求",
        requirement_type="FEATURE",
        status=requirement_status,
        description="d",
        created_by=boss_id,
        updated_by=boss_id,
    )
    feedback = Feedback(
        feedback_no="FB-1",
        title="反馈",
        feedback_type="SYSTEM_ISSUE",
        status=FeedbackStatus.REQUIREMENT_LINKED,
        submitter_id=boss_id,
        description="d",
        created_by=boss_id,
        updated_by=boss_id,
    )
    session.add_all([version, requirement, feedback])
    session.flush()
    requirement.current_version_id = version.id
    feedback.main_requirement_id = requirement.id
    session.add_all(
        [
            VersionRequirement(
                version_id=version.id, requirement_id=requirement.id, added_by=boss_id
            ),
            RequirementFeedback(
                requirement_id=requirement.id, feedback_id=feedback.id, is_primary=True
            ),
        ]
    )
    session.commit()
    return {"version": version.id, "requirement": requirement.id, "feedback": feedback.id}


def _publish_body(revision: int = 1) -> dict:
    return {
        "released_at": datetime.now(UTC).isoformat(),
        "release_notes": "首次发布",
        "revision": revision,
    }


# --------------------------------------------------------------------------- #
def test_publish_success_syncs_version_requirement_feedback_and_release(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])

    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["release"]["result"] == "SUCCESS"
    assert body["release"]["version_id"] == seeded["version"]
    assert body["released_requirement_ids"] == [seeded["requirement"]]
    assert body["online_feedback_ids"] == [seeded["feedback"]]

    session.expire_all()
    assert session.get(Version, seeded["version"]).status == VersionStatus.RELEASED
    assert session.get(Requirement, seeded["requirement"]).status == RequirementStatus.ONLINE
    assert session.get(Feedback, seeded["feedback"]).status == FeedbackStatus.ONLINE
    assert (
        session.scalar(select(Release).where(Release.version_id == seeded["version"])) is not None
    )
    # submitter got an in-app notification
    assert (
        session.scalar(select(Notification).where(Notification.entity_id == seeded["feedback"]))
        is not None
    )


def test_publish_blocked_by_unfinished_requirement(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(
        session, ids["boss"], requirement_status=RequirementStatus.DEVELOPING
    )
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(),
    )
    assert resp.status_code == 409
    blocking = resp.json()["data"]["blocking_requirements"]
    assert blocking[0]["id"] == seeded["requirement"]
    assert blocking[0]["status"] == "DEVELOPING"
    # nothing changed
    session.expire_all()
    assert session.get(Version, seeded["version"]).status == VersionStatus.READY
    assert session.scalar(select(Release)) is None


def test_publish_requires_permission(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["member"],
        json=_publish_body(),
    )
    assert resp.status_code == 403


def test_second_publish_conflicts(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    first = client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(),
    )
    assert first.status_code == 200
    # A second publish (version no longer READY) is rejected.
    second = client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(revision=2),
    )
    assert second.status_code == 409


def test_publish_rolls_back_when_release_insert_fails(pub_api):
    _client, session, _headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    service = VersionService(session)
    with patch("app.services.version_service.Release", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            service.publish(
                seeded["version"], PublishVersionRequest(**_publish_body()), ids["boss"]
            )
    session.rollback()
    session.expire_all()
    # The version flip + requirement/feedback changes were never committed.
    assert session.get(Version, seeded["version"]).status == VersionStatus.READY
    assert session.get(Requirement, seeded["requirement"]).status == RequirementStatus.DONE
    assert session.get(Feedback, seeded["feedback"]).status == FeedbackStatus.REQUIREMENT_LINKED
    assert session.scalar(select(Release)) is None


def test_publish_audit_chain(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(),
    )
    actions = {(log.entity_type, log.action) for log in session.scalars(select(OperationLog)).all()}
    assert ("VERSION", "VERSION_PUBLISH") in actions
    assert ("RELEASE", "RELEASE_CREATE") in actions
    assert ("REQUIREMENT", "STATUS_CHANGE") in actions
    assert ("FEEDBACK", "STATUS_CHANGE") in actions
    blob = str(
        [(log.before_data, log.after_data) for log in session.scalars(select(OperationLog)).all()]
    )
    for secret in ("password", "token", "Bearer"):
        assert secret not in blob


# --------------------------------------------------------------------------- #
# Publish check                                                               #
# --------------------------------------------------------------------------- #
def test_publish_check_passes_when_ready_and_all_done(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish/check", headers=headers["boss"]
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["passed"] is True
    types = {c["type"]: c["passed"] for c in body["checks"]}
    assert types == {
        "VERSION_STATUS_CHECK": True,
        "REQUIREMENT_STATUS_CHECK": True,
        "PERMISSION_CHECK": True,
    }


def test_publish_check_fails_when_not_ready(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"], version_status=VersionStatus.PLANNING)
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish/check", headers=headers["boss"]
    )
    assert resp.status_code == 409
    checks = {c["type"]: c["passed"] for c in resp.json()["data"]["checks"]}
    assert checks["VERSION_STATUS_CHECK"] is False


def test_publish_check_fails_with_blocking_requirements(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"], requirement_status=RequirementStatus.TESTING)
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish/check", headers=headers["boss"]
    )
    assert resp.status_code == 409
    blocking = resp.json()["data"]["blocking_requirements"]
    assert blocking[0]["id"] == seeded["requirement"]
    assert blocking[0]["status"] == "TESTING"


def test_publish_check_requires_permission(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    resp = client.post(
        f"/api/v1/versions/{seeded['version']}/publish/check", headers=headers["member"]
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Release history                                                             #
# --------------------------------------------------------------------------- #
def test_release_history_list_detail_and_filter(pub_api):
    client, session, headers, ids = pub_api
    seeded = _seed_ready_version(session, ids["boss"])
    client.post(
        f"/api/v1/versions/{seeded['version']}/publish",
        headers=headers["boss"],
        json=_publish_body(),
    )
    listed = client.get("/api/v1/releases", headers=headers["boss"]).json()
    assert listed["total"] == 1
    release_id = listed["items"][0]["id"]
    assert listed["items"][0]["result"] == "SUCCESS"

    # version_id filter
    filtered = client.get(
        f"/api/v1/releases?version_id={seeded['version']}", headers=headers["boss"]
    ).json()
    assert filtered["total"] == 1
    empty = client.get("/api/v1/releases?version_id=999999", headers=headers["boss"]).json()
    assert empty["total"] == 0

    # detail
    detail = client.get(f"/api/v1/releases/{release_id}", headers=headers["boss"])
    assert detail.status_code == 200
    assert detail.json()["version_id"] == seeded["version"]
    assert client.get("/api/v1/releases/999999", headers=headers["boss"]).status_code == 404


@pytest.mark.parametrize("spec_name", ["openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"])
def test_openapi_declares_publish_contract(spec_name):
    spec = yaml.safe_load((SPEC_DIR / spec_name).read_text(encoding="utf-8"))
    publish = spec["paths"]["/versions/{version_id}/publish"]["post"]
    assert "post" in spec["paths"]["/versions/{version_id}/publish/check"]
    assert "get" in spec["paths"]["/releases/{release_id}"]
    assert "PublishCheckResult" in spec["components"]["schemas"]
    assert publish["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "PublishResult"
    )
    schemas = spec["components"]["schemas"]
    assert "PublishResult" in schemas and "ReleaseOut" in schemas
    # Release stays a record-type entity: no workflow status field.
    assert "status" not in schemas["ReleaseOut"]["properties"]

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    Feedback,
    Permission,
    Release,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    FeedbackType,
    ReleaseResult,
    RequirementStatus,
    UserStatus,
    VersionStatus,
)

DashboardFixture = tuple[TestClient, dict[str, dict[str, str]]]


@pytest.fixture
def dashboard_api(tmp_path: Path) -> Iterator[DashboardFixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'dashboard-api.db'}",
        connect_args={"check_same_thread": False},
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        Feedback.__table__,
        Requirement.__table__,
        Version.__table__,
        Release.__table__,
    ):
        table.create(engine)

    user_definitions = {
        "no_dashboard": (1, DataScope.ALL, {"rd.feedback.view"}),
        "dashboard_only": (2, DataScope.ALL, {"dashboard.view"}),
        "feedback_all": (3, DataScope.ALL, {"dashboard.view", "rd.feedback.view"}),
        "feedback_self": (4, DataScope.SELF, {"dashboard.view", "rd.feedback.view"}),
        "requirement_self": (5, DataScope.SELF, {"dashboard.view", "rd.requirement.view"}),
        "version_self": (6, DataScope.SELF, {"dashboard.view", "rd.version.view"}),
        "release_self": (7, DataScope.SELF, {"dashboard.view", "rd.release.view"}),
        "wildcard": (8, DataScope.ALL, {"*"}),
        "other": (9, DataScope.SELF, set()),
    }
    permission_codes = sorted(
        {code for _id, _scope, codes in user_definitions.values() for code in codes}
    )

    with Session(engine, expire_on_commit=False) as session:
        permissions = {
            code: Permission(id=index, code=code, name=code)
            for index, code in enumerate(permission_codes, start=1)
        }
        session.add_all(permissions.values())

        users: dict[str, User] = {}
        roles: dict[str, Role] = {}
        for name, (user_id, data_scope, codes) in user_definitions.items():
            user = User(
                id=user_id,
                username=name,
                display_name=name,
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            role = Role(
                id=100 + user_id,
                code=f"ROLE_{name.upper()}",
                name=name,
                data_scope=data_scope,
                enabled=True,
            )
            users[name] = user
            roles[name] = role
            session.add_all([user, role])
            session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
            session.add_all(
                RolePermission(role_id=role.id, permission_id=permissions[code].id)
                for code in codes
            )

        base_time = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
        session.add_all(
            [
                Feedback(
                    id=1,
                    feedback_no="FB-001",
                    title="Self new",
                    feedback_type=FeedbackType.NEW_FEATURE,
                    status=FeedbackStatus.NEW,
                    submitter_id=users["feedback_self"].id,
                    description="feedback",
                ),
                Feedback(
                    id=2,
                    feedback_no="FB-002",
                    title="Self accepted",
                    feedback_type=FeedbackType.NEW_FEATURE,
                    status=FeedbackStatus.ACCEPTED,
                    submitter_id=users["feedback_self"].id,
                    description="feedback",
                ),
                Feedback(
                    id=3,
                    feedback_no="FB-003",
                    title="Self online",
                    feedback_type=FeedbackType.NEW_FEATURE,
                    status=FeedbackStatus.ONLINE,
                    submitter_id=users["feedback_self"].id,
                    description="feedback",
                ),
                Feedback(
                    id=4,
                    feedback_no="FB-004",
                    title="Other new",
                    feedback_type=FeedbackType.NEW_FEATURE,
                    status=FeedbackStatus.NEW,
                    submitter_id=users["other"].id,
                    description="feedback",
                ),
                Feedback(
                    id=5,
                    feedback_no="FB-005",
                    title="Other closed",
                    feedback_type=FeedbackType.NEW_FEATURE,
                    status=FeedbackStatus.CLOSED,
                    submitter_id=users["other"].id,
                    description="feedback",
                ),
            ]
        )

        requirement_rows = [
            (10, RequirementStatus.CONFIRMED, users["requirement_self"].id, users["other"].id),
            (11, RequirementStatus.PLANNED, users["other"].id, users["requirement_self"].id),
            (12, RequirementStatus.DEVELOPING, users["other"].id, users["other"].id),
            (13, RequirementStatus.DRAFT, users["requirement_self"].id, users["other"].id),
            (14, RequirementStatus.DONE, users["other"].id, users["requirement_self"].id),
        ]
        session.add_all(
            Requirement(
                id=item_id,
                requirement_no=f"REQ-{item_id}",
                title=f"Requirement {item_id}",
                requirement_type="FEATURE",
                status=status,
                owner_id=owner_id,
                created_by=created_by,
                description="requirement",
            )
            for item_id, status, owner_id, created_by in requirement_rows
        )

        active_statuses = [
            VersionStatus.PLANNING,
            VersionStatus.DEVELOPING,
            VersionStatus.TESTING,
            VersionStatus.READY,
            VersionStatus.PLANNING,
            VersionStatus.DEVELOPING,
            VersionStatus.TESTING,
        ]
        active_versions = []
        for offset, status in enumerate(active_statuses):
            item_id = 20 + offset
            active_versions.append(
                Version(
                    id=item_id,
                    version_no=f"V-{item_id}",
                    name=f"Visible active {item_id}",
                    status=status,
                    owner_id=users["version_self"].id if offset % 2 == 0 else users["other"].id,
                    created_by=users["version_self"].id if offset % 2 else users["other"].id,
                    planned_release_date=date(2026, 10, 1) + timedelta(days=offset),
                    created_at=base_time,
                    updated_at=base_time + timedelta(minutes=offset),
                )
            )
        session.add_all(
            [
                *active_versions,
                Version(
                    id=27,
                    version_no="V-27",
                    name="Visible released",
                    status=VersionStatus.RELEASED,
                    owner_id=users["version_self"].id,
                    created_at=base_time,
                    updated_at=base_time,
                ),
                Version(
                    id=28,
                    version_no="V-28",
                    name="Visible canceled",
                    status=VersionStatus.CANCELED,
                    created_by=users["version_self"].id,
                    created_at=base_time,
                    updated_at=base_time,
                ),
                Version(
                    id=29,
                    version_no="V-29",
                    name="Other active",
                    status=VersionStatus.READY,
                    owner_id=users["other"].id,
                    created_by=users["other"].id,
                    created_at=base_time,
                    updated_at=base_time + timedelta(days=1),
                ),
            ]
        )

        release_versions = []
        releases = []
        for offset in range(6):
            version_id = 40 + offset
            release_versions.append(
                Version(
                    id=version_id,
                    version_no=f"V-{version_id}",
                    name=f"Released {version_id}",
                    status=VersionStatus.RELEASED,
                    owner_id=users["release_self"].id,
                    created_at=base_time,
                    updated_at=base_time,
                )
            )
            releases.append(
                Release(
                    id=50 + offset,
                    version_id=version_id,
                    released_at=base_time + timedelta(days=offset),
                    result=ReleaseResult.SUCCESS,
                    release_notes="released",
                )
            )
        session.add_all(
            [
                *release_versions,
                *releases,
                Version(
                    id=46,
                    version_no="V-46",
                    name="Other release",
                    status=VersionStatus.RELEASED,
                    owner_id=users["other"].id,
                    created_by=users["other"].id,
                    created_at=base_time,
                    updated_at=base_time,
                ),
                Release(
                    id=56,
                    version_id=46,
                    released_at=base_time + timedelta(days=10),
                    result=ReleaseResult.SUCCESS,
                    release_notes="other released",
                ),
            ]
        )
        session.commit()

        headers = {
            name: {"Authorization": f"Bearer {create_access_token(user.id)}"}
            for name, user in users.items()
        }
        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, headers
        app.dependency_overrides.clear()

    engine.dispose()


def test_dashboard_permission_does_not_replace_domain_permissions(
    dashboard_api: DashboardFixture,
):
    client, headers = dashboard_api

    assert (
        client.get("/api/v1/dashboard/overview", headers=headers["no_dashboard"]).status_code == 403
    )

    response = client.get("/api/v1/dashboard/overview", headers=headers["dashboard_only"])
    assert response.status_code == 200
    assert response.json() == {
        "data_scope": "ALL",
        "feedback": None,
        "requirements": None,
        "versions": None,
        "releases": None,
    }


def test_feedback_overview_is_permission_and_scope_aware(dashboard_api: DashboardFixture):
    client, headers = dashboard_api

    all_overview = client.get("/api/v1/dashboard/overview", headers=headers["feedback_all"]).json()
    assert all_overview["feedback"]["total_count"] == 5
    assert all_overview["feedback"]["pending_count"] == 3
    assert set(all_overview["feedback"]["by_status"]) == {status.value for status in FeedbackStatus}
    assert all_overview["feedback"]["by_status"]["CANNOT_REPRODUCE"] == 0
    assert all_overview["requirements"] is None
    assert all_overview["versions"] is None
    assert all_overview["releases"] is None

    self_overview = client.get(
        "/api/v1/dashboard/overview", headers=headers["feedback_self"]
    ).json()
    assert self_overview["data_scope"] == "SELF"
    assert self_overview["feedback"]["total_count"] == 3
    assert self_overview["feedback"]["pending_count"] == 2


def test_requirement_self_scope_and_active_definition(dashboard_api: DashboardFixture):
    client, headers = dashboard_api
    overview = client.get("/api/v1/dashboard/overview", headers=headers["requirement_self"]).json()

    assert overview["requirements"]["total_count"] == 4
    assert overview["requirements"]["active_count"] == 2
    assert set(overview["requirements"]["by_status"]) == {
        status.value for status in RequirementStatus
    }
    assert overview["requirements"]["by_status"]["DEVELOPING"] == 0


def test_version_self_scope_active_definition_and_stable_recent_limit(
    dashboard_api: DashboardFixture,
):
    client, headers = dashboard_api
    overview = client.get("/api/v1/dashboard/overview", headers=headers["version_self"]).json()
    versions = overview["versions"]

    assert versions["total_count"] == 9
    assert versions["active_count"] == 7
    assert set(versions["by_status"]) == {status.value for status in VersionStatus}
    recent = versions["recent_active_versions"]
    assert len(recent) == 5
    assert [item["id"] for item in recent] == [26, 25, 24, 23, 22]
    assert all(item["status"] in {"PLANNING", "DEVELOPING", "TESTING", "READY"} for item in recent)


def test_release_self_scope_and_stable_recent_limit(dashboard_api: DashboardFixture):
    client, headers = dashboard_api
    overview = client.get("/api/v1/dashboard/overview", headers=headers["release_self"]).json()
    releases = overview["releases"]

    assert releases["total_count"] == 6
    assert len(releases["recent_releases"]) == 5
    assert [item["id"] for item in releases["recent_releases"]] == [55, 54, 53, 52, 51]
    assert all("release_notes" not in item for item in releases["recent_releases"])


def test_wildcard_returns_all_dashboard_sections(dashboard_api: DashboardFixture):
    client, headers = dashboard_api
    response = client.get("/api/v1/dashboard/overview", headers=headers["wildcard"])

    assert response.status_code == 200
    assert response.json()["data_scope"] == "ALL"
    assert all(
        response.json()[section] is not None
        for section in ("feedback", "requirements", "versions", "releases")
    )


def test_dashboard_openapi_contract_is_synchronized():
    dynamic = app.openapi()
    operation = dynamic["paths"]["/api/v1/dashboard/overview"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DashboardOverviewOut"
    }
    dynamic_schema = dynamic["components"]["schemas"]["DashboardOverviewOut"]
    assert dynamic_schema["required"] == [
        "data_scope",
        "feedback",
        "requirements",
        "versions",
        "releases",
    ]

    spec_dir = Path(__file__).resolve().parents[2] / "spec"
    for filename in ("openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"):
        document = yaml.safe_load((spec_dir / filename).read_text(encoding="utf-8"))
        assert document["paths"]["/dashboard/overview"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"] == {"$ref": "#/components/schemas/DashboardOverview"}
        schema = document["components"]["schemas"]["DashboardOverview"]
        assert schema["required"] == [
            "data_scope",
            "feedback",
            "requirements",
            "versions",
            "releases",
        ]

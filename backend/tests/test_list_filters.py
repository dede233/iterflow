from datetime import UTC, date, datetime

import pytest
from test_requirement_api import req_api as req_api
from test_version_api import ver_api as ver_api

from app.models.entities import Requirement, Version
from app.models.enums import Priority, RequirementSource, RequirementStatus, VersionStatus


@pytest.fixture
def requirement_filters(req_api):
    client, session, headers, ids = req_api
    items = []
    for index, (number, title, owner, creator) in enumerate(
        [
            ("Req_MiXeD", "Alpha Search", "alice", "boss"),
            ("REQ-B2", "Beta 50% Control", "bob", "alice"),
            ("REQ-C3", "Hidden Alpha", "bob", "boss"),
            ("REQ-D4", "Alpha Extra", None, "boss"),
        ]
    ):
        item = Requirement(
            requirement_no=number,
            title=title,
            requirement_type="FEATURE",
            description="description-only-token",
            acceptance_criteria="acceptance-only-token",
            status=RequirementStatus.DRAFT if index == 1 else RequirementStatus.CONFIRMED,
            priority=Priority.P2 if index == 1 else Priority.P1,
            source=RequirementSource.DIRECT if index == 1 else RequirementSource.FEEDBACK,
            current_version_id=43 if index == 1 else 42,
            owner_id=ids[owner] if owner else None,
            created_by=ids[creator],
            created_at=datetime(2026, 1, 2 if index == 3 else 1, tzinfo=UTC),
        )
        session.add(item)
        items.append(item)
    session.commit()
    return client, headers, ids, items


@pytest.mark.parametrize(
    ("params", "indices"),
    [
        ({"keyword": "req_mixed"}, [0]),
        ({"keyword": "ALPHA"}, [3, 2, 0]),
        ({"keyword": "  alpha  "}, [3, 2, 0]),
        ({"keyword": "  "}, [3, 2, 1, 0]),
        ({"keyword": "description-only-token"}, []),
        ({"keyword": "acceptance-only-token"}, []),
        ({"keyword": "%"}, [1]),
        ({"keyword": "_"}, [0]),
        ({"status": "DRAFT"}, [1]),
        ({"priority": "P1"}, [3, 2, 0]),
        ({"source": "DIRECT"}, [1]),
        ({"current_version_id": 42}, [3, 2, 0]),
        ({"owner_id": 3}, [2, 1]),
        ({"current_version_id": 999999}, []),
        ({"owner_id": 999999}, []),
        (
            {
                "keyword": "alpha",
                "status": "CONFIRMED",
                "priority": "P1",
                "source": "FEEDBACK",
                "current_version_id": 42,
                "owner_id": 2,
            },
            [0],
        ),
    ],
)
def test_requirement_filters_without_cross_domain_permissions(requirement_filters, params, indices):
    client, headers, _ids, items = requirement_filters
    # This role has only rd.requirement.view, with no Version or User permissions.
    response = client.get("/api/v1/requirements", params=params, headers=headers["reader"])
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [items[i].id for i in indices]
    assert response.json()["total"] == len(indices)


def test_requirement_filter_pagination_total_and_stable_order(requirement_filters):
    client, headers, _ids, items = requirement_filters
    pages = [
        client.get(
            "/api/v1/requirements",
            params={"keyword": "alpha", "page": page, "page_size": 2},
            headers=headers["boss"],
        ).json()
        for page in (1, 2)
    ]
    assert [page["total"] for page in pages] == [3, 3]
    assert [row["id"] for page in pages for row in page["items"]] == [
        items[i].id for i in (3, 2, 0)
    ]


def test_requirement_filters_and_scope_are_combined(requirement_filters):
    client, headers, ids, items = requirement_filters
    owner = client.get(
        "/api/v1/requirements", params={"owner_id": ids["bob"]}, headers=headers["alice"]
    )
    assert owner.status_code == 200
    assert owner.json()["total"] == 1
    assert owner.json()["items"][0]["id"] == items[1].id  # created by Alice, owned by Bob
    hidden = client.get(
        "/api/v1/requirements",
        params={"owner_id": ids["bob"], "keyword": "alpha", "current_version_id": 42},
        headers=headers["alice"],
    )
    assert hidden.json()["items"] == []
    assert hidden.json()["total"] == 0
    visible = client.get(
        "/api/v1/requirements", params={"keyword": "alpha"}, headers=headers["alice"]
    )
    assert visible.json()["total"] == 1
    assert visible.json()["items"][0]["id"] == items[0].id
    assert (
        client.get(
            "/api/v1/requirements", params={"keyword": "alpha"}, headers=headers["converter"]
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "params",
    [
        {"owner_id": 0},
        {"current_version_id": -1},
        {"status": "INVALID"},
        {"priority": "P5"},
        {"source": "INVALID"},
        {"keyword": "x" * 201},
    ],
)
def test_requirement_filter_validation(requirement_filters, params):
    client, headers, _ids, _items = requirement_filters
    response = client.get("/api/v1/requirements", params=params, headers=headers["boss"])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.fixture
def version_filters(ver_api):
    client, session, headers, ids = ver_api
    items = []
    for index, (number, name, owner, creator) in enumerate(
        [
            ("Ver_MiXeD", "Alpha Release", "alice", "boss"),
            ("V2", "Beta Control", "bob", "alice"),
            ("V3", "Hidden Alpha 50%", "bob", "boss"),
            ("V4", "No planned date", None, "boss"),
        ]
    ):
        item = Version(
            version_no=number,
            name=name,
            description="description-only-token",
            status=VersionStatus.RELEASED if index in (0, 2) else VersionStatus.PLANNING,
            planned_release_date=date(2026, 10, index + 1) if index < 3 else None,
            owner_id=ids[owner] if owner else None,
            created_by=ids[creator],
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add(item)
        items.append(item)
    session.commit()
    return client, headers, ids, items


@pytest.mark.parametrize(
    ("params", "indices"),
    [
        ({"keyword": "ver_mixed"}, [0]),
        ({"keyword": "ALPHA"}, [2, 0]),
        ({"keyword": "  alpha  "}, [2, 0]),
        ({"keyword": "  "}, [3, 2, 1, 0]),
        ({"keyword": "description-only-token"}, []),
        ({"keyword": "%"}, [2]),
        ({"keyword": "_"}, [0]),
        ({"status": "RELEASED"}, [2, 0]),
        ({"planned_release_from": "2026-10-02"}, [2, 1]),
        ({"planned_release_to": "2026-10-02"}, [1, 0]),
        ({"planned_release_from": "2026-10-01", "planned_release_to": "2026-10-03"}, [2, 1, 0]),
        ({"planned_release_from": "2026-10-02", "planned_release_to": "2026-10-02"}, [1]),
        ({"owner_id": 3}, [2, 1]),
        ({"owner_id": 999999}, []),
        (
            {
                "keyword": "alpha",
                "status": "RELEASED",
                "planned_release_from": "2026-10-01",
                "planned_release_to": "2026-10-01",
                "owner_id": 2,
            },
            [0],
        ),
    ],
)
def test_version_filters_without_user_permissions(version_filters, params, indices):
    client, headers, _ids, items = version_filters
    response = client.get("/api/v1/versions", params=params, headers=headers["version_editor"])
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [items[i].id for i in indices]
    assert response.json()["total"] == len(indices)


def test_version_filter_pagination_total_and_stable_order(version_filters):
    client, headers, _ids, items = version_filters
    pages = [
        client.get(
            "/api/v1/versions",
            params={"status": "RELEASED", "page": page, "page_size": 1},
            headers=headers["boss"],
        ).json()
        for page in (1, 2)
    ]
    assert [page["total"] for page in pages] == [2, 2]
    assert [row["id"] for page in pages for row in page["items"]] == [items[2].id, items[0].id]


def test_version_filters_and_scope_are_combined(version_filters):
    client, headers, ids, items = version_filters
    owner = client.get(
        "/api/v1/versions", params={"owner_id": ids["bob"]}, headers=headers["alice"]
    )
    assert owner.status_code == 200
    assert owner.json()["total"] == 1
    assert owner.json()["items"][0]["id"] == items[1].id
    hidden = client.get(
        "/api/v1/versions",
        params={"owner_id": ids["bob"], "planned_release_from": "2026-10-03"},
        headers=headers["alice"],
    )
    assert hidden.json()["items"] == []
    assert hidden.json()["total"] == 0
    visible = client.get(
        "/api/v1/versions",
        params={"keyword": "alpha", "status": "RELEASED"},
        headers=headers["alice"],
    )
    assert visible.json()["total"] == 1
    assert visible.json()["items"][0]["id"] == items[0].id


@pytest.mark.parametrize(
    "params",
    [
        {"planned_release_from": "2026-10-03", "planned_release_to": "2026-10-01"},
        {"planned_release_from": "invalid"},
        {"owner_id": 0},
        {"status": "INVALID"},
        {"keyword": "x" * 201},
    ],
)
def test_version_filter_validation(version_filters, params):
    client, headers, _ids, _items = version_filters
    response = client.get("/api/v1/versions", params=params, headers=headers["boss"])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)

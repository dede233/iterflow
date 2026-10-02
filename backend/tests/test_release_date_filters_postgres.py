"""Real PostgreSQL date precision, offset normalization and Version scope."""

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session
from test_release_readiness_postgres import actor
from test_v1_e2e_postgres import postgres_e2e_engine as postgres_e2e_engine
from test_v1_e2e_postgres import postgres_http_client as postgres_http_client

from app.models.entities import Release, Version
from app.models.enums import DataScope


@pytest.fixture
def dates(postgres_e2e_engine, postgres_http_client):
    engine, _, _ = postgres_e2e_engine
    with Session(engine) as db:
        actors = {
            name: actor(db, codes, scope)
            for name, codes, scope in [
                ("self", {"rd.release.view"}, DataScope.SELF),
                ("other", {"rd.release.view"}, DataScope.SELF),
                ("all", {"rd.release.view"}, DataScope.ALL),
                ("none", set(), DataScope.ALL),
            ]
        }
        items = []
        for index, instant in enumerate(
            [
                "2090-09-30T23:59:59.999999+00:00",
                "2090-10-01T00:00:00+00:00",
                "2090-10-01T23:59:59.999999+00:00",
                "2090-10-02T00:00:00+00:00",
                "2090-10-02T00:00:00+00:00",
                "2090-10-03T00:00:00+00:00",
            ]
        ):
            owner = actors["other" if index in (2, 4) else "self"][0]
            v = Version(version_no=uuid4().hex, name="Date fixture", created_by=owner)
            db.add(v)
            db.flush()
            row = Release(
                version_id=v.id, released_at=datetime.fromisoformat(instant), release_notes="date"
            )
            db.add(row)
            db.flush()
            items.append((row.id, v.id))
        db.commit()
    yield postgres_http_client, {name: value[1] for name, value in actors.items()}, items
    with Session(engine) as db:
        db.execute(delete(Release).where(Release.id.in_([i[0] for i in items])))
        db.execute(delete(Version).where(Version.id.in_([i[1] for i in items])))
        db.commit()


@pytest.mark.parametrize(
    ("params", "indices"),
    [
        (
            {"released_from": "2090-10-01T00:00:00Z", "released_before": "2090-10-02T00:00:00Z"},
            [2, 1],
        ),
        (
            {
                "released_from": "2090-10-01T08:00:00+08:00",
                "released_before": "2090-10-02T08:00:00+08:00",
            },
            [2, 1],
        ),
        ({"released_from": "2090-10-01T00:00:00Z"}, [5, 4, 3, 2, 1]),
        ({"released_before": "2090-10-01T00:00:00Z"}, [0]),
        (
            {
                "released_from": "2090-10-01T23:59:59.999999Z",
                "released_before": "2090-10-02T00:00:00Z",
            },
            [2],
        ),
        ({"released_from": "2091-01-01T00:00:00Z"}, []),
    ],
)
def test_date_bounds_total_pagination_and_permission(dates, params, indices):
    client, headers, items = dates
    pages = [
        client.get(
            "/api/v1/releases", params={**params, "page": p, "page_size": 1}, headers=headers["all"]
        )
        for p in range(1, max(len(indices), 1) + 1)
    ]
    assert all(p.status_code == 200 for p in pages)
    assert all(p.json()["total"] == len(indices) for p in pages)
    assert [row["id"] for p in pages for row in p.json()["items"]] == [items[i][0] for i in indices]
    own = client.get("/api/v1/releases", params=params, headers=headers["self"]).json()
    visible = [i for i in indices if i not in (2, 4)]
    assert own["total"] == len(visible)
    assert [row["id"] for row in own["items"]] == [items[i][0] for i in visible]
    assert client.get("/api/v1/releases", params=params, headers=headers["none"]).status_code == 403
    scoped = client.get(
        "/api/v1/releases", params={**params, "version_id": items[2][1]}, headers=headers["self"]
    ).json()
    assert scoped["items"] == [] and scoped["total"] == 0
    all_version = client.get(
        "/api/v1/releases", params={**params, "version_id": items[2][1]}, headers=headers["all"]
    ).json()
    assert all_version["total"] == int(2 in indices)
    assert [r["id"] for r in all_version["items"]] == ([items[2][0]] if 2 in indices else [])


@pytest.mark.parametrize(
    "params",
    [
        {"released_from": "2090-10-02T00:00:00Z", "released_before": "2090-10-02T00:00:00Z"},
        {"released_from": "2090-10-03T00:00:00Z", "released_before": "2090-10-02T00:00:00Z"},
        {"released_from": "2090-10-02T08:00:00+08:00", "released_before": "2090-10-02T00:00:00Z"},
        {"released_from": "2090-10-01T00:00:00"},
        {"released_before": "2090-10-02"},
        {"released_from": "1735689600"},
        {"released_from": "invalid"},
    ],
)
def test_date_query_validation(dates, params):
    client, headers, _ = dates
    response = client.get("/api/v1/releases", params=params, headers=headers["all"])
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)

"""Real-database projection and publication races on disposable test fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Release, Requirement, Version, VersionRequirement


def exercise_version_progress(fixture, scenario):
    client, engine, uid, headers = fixture

    def create_requirement(title):
        response = client.post(
            "/api/v1/requirements",
            headers=headers,
            json={
                "title": title,
                "requirement_type": "FEATURE",
                "description": "正常接口验收内容",
                "participants": [
                    {"role": role, "user_id": uid} for role in ("CONFIRM", "DEVELOP", "ACCEPT")
                ],
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    requirement = create_requirement("版本自动进度需求")
    created = client.post(
        "/api/v1/versions",
        headers=headers,
        json={
            "version_no": "PROGRESS-REAL",
            "name": "自动汇总版本",
            "requirement_id": requirement["id"],
            "requirement_revision": requirement["revision"],
        },
    )
    assert created.status_code == 200, created.text
    version = created.json()
    vid = version["id"]
    rid = requirement["id"]

    def check_progress(expected):
        current = client.get(f"/api/v1/versions/{vid}", headers=headers)
        assert current.status_code == 200 and current.json()["status"] == expected, current.text
        filtered = client.get("/api/v1/versions", headers=headers, params={"status": expected})
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == 1 and filtered.json()["items"][0]["id"] == vid
        dashboard = client.get("/api/v1/dashboard/overview", headers=headers)
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["versions"]["by_status"][expected] == 1
        assert dashboard.json()["versions"]["recent_active_versions"][0]["status"] == expected
        with Session(engine) as db:
            stored = db.get(Version, vid)
            assert stored.status == "PLANNING" and stored.revision == version["revision"]

    if scenario == "projection":
        check_progress("PLANNING")
    requirement = client.get(f"/api/v1/requirements/{rid}", headers=headers).json()
    confirmed = client.post(
        f"/api/v1/requirements/{rid}/workflow",
        headers=headers,
        json={"action": "CONFIRM", "revision": requirement["revision"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    if scenario == "projection":
        check_progress("PLANNING")
    for target, expected in [
        ("DEVELOPING", "DEVELOPING"),
        ("TESTING", "TESTING"),
        ("DONE", "READY"),
    ]:
        requirement = client.get(f"/api/v1/requirements/{rid}", headers=headers).json()
        changed = client.patch(
            f"/api/v1/requirements/{rid}/status",
            headers=headers,
            json={"status": target, "revision": requirement["revision"]},
        )
        assert changed.status_code == 200, changed.text
        requirement = changed.json()
        if scenario == "projection":
            check_progress(expected)

    edit_payload = {"description": "修改后的验收范围", "revision": requirement["revision"]}
    publish_payload = {
        "revision": version["revision"],
        "released_at": datetime.now(UTC).isoformat(),
        "release_notes": "隔离发布竞争验证",
    }
    if scenario == "projection":
        edited = client.patch(f"/api/v1/requirements/{rid}", headers=headers, json=edit_payload)
        assert edited.status_code == 200, edited.text
        check_progress("TESTING")
        blocked = client.post(
            f"/api/v1/versions/{vid}/publish", headers=headers, json=publish_payload
        )
        assert blocked.status_code == 409, blocked.text
        confirmed = client.post(
            f"/api/v1/requirements/{rid}/workflow",
            headers=headers,
            json={"action": "CONFIRM", "revision": edited.json()["revision"]},
        )
        assert confirmed.status_code == 200, confirmed.text
        check_progress("READY")
        return

    other = create_requirement("竞争新增需求") if scenario == "roster_publish_race" else None
    barrier = Barrier(2)

    def publish():
        barrier.wait(timeout=10)
        return client.post(f"/api/v1/versions/{vid}/publish", headers=headers, json=publish_payload)

    def competing_write():
        barrier.wait(timeout=10)
        if scenario == "publish_race":
            return client.post(
                f"/api/v1/versions/{vid}/publish", headers=headers, json=publish_payload
            )
        if scenario == "content_publish_race":
            return client.patch(f"/api/v1/requirements/{rid}", headers=headers, json=edit_payload)
        if scenario == "cancel_publish_race":
            return client.patch(
                f"/api/v1/versions/{vid}/status",
                headers=headers,
                json={
                    "status": "CANCELED",
                    "revision": version["revision"],
                    "reason": "停止本次发布",
                },
            )
        assert scenario == "roster_publish_race" and other is not None
        return client.post(
            f"/api/v1/versions/{vid}/requirements",
            headers=headers,
            json={
                "requirement_id": other["id"],
                "revision": other["revision"],
                "version_revision": version["revision"],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(publish)
        second = pool.submit(competing_write)
        published, competed = first.result(timeout=30), second.result(timeout=30)
    assert sorted([published.status_code, competed.status_code]) == [200, 409], (
        published.text,
        competed.text,
    )
    with Session(engine) as db:
        stored = db.get(Version, vid)
        req = db.get(Requirement, rid)
        releases = db.scalar(select(func.count(Release.id)).where(Release.version_id == vid))
        did_publish = published.status_code == 200 or scenario == "publish_race"
        if did_publish:
            assert stored.status == "RELEASED" and req.status == "ONLINE" and releases == 1
        else:
            assert stored.status != "RELEASED" and req.status == "DONE" and releases == 0
            if scenario == "content_publish_race":
                assert req.confirmed_revision != req.content_revision
            if scenario == "cancel_publish_race":
                assert stored.status == "CANCELED"
        if other is not None:
            linked = db.get(Requirement, other["id"])
            assert linked.current_version_id == (None if did_publish else vid)
            assert db.scalar(
                select(func.count(VersionRequirement.id)).where(
                    VersionRequirement.version_id == vid, VersionRequirement.active.is_(True)
                )
            ) == (1 if did_publish else 2)

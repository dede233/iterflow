"""Atomic brand editing and independent platform publication on disposable databases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from app.core.security import create_access_token
from app.models.entities import (
    Notification,
    OperationLog,
    Release,
    ReleaseBatchTarget,
    ReleaseTarget,
    Requirement,
    User,
    Version,
    VersionRequirement,
)
from app.schemas.target_release import MiniProgramTargetUpdate
from app.services.audit_service import AuditService
from app.services.target_release_service import TargetReleaseService

GROUP_SCENARIOS = [
    "create_edit",
    "legacy",
    "conflicts",
    "rollback",
    "race",
    "publication",
    "permissions",
    "create_race",
    "membership_change",
]


def exercise_grouped(fixture, scenario, monkeypatch):
    client, engine, uid, headers = fixture
    sid = create_test_system(engine)

    def request(method, path, body=None, status=200, auth=headers):
        response = client.request(method, "/api/v1" + path, json=body, headers=auth)
        assert response.status_code == status, response.text
        return response.json()

    def config(code="BRAND", name="Brand", both=True):
        platforms = [{"platform": "WECHAT_MINI_PROGRAM", "app_id": "wx1234567890abcdef"}]
        if both:
            platforms.append({"platform": "ALIPAY_MINI_PROGRAM", "app_id": "2021000000000001"})
        return dict(code=code, name=name, platforms=platforms)

    path = f"/systems/{sid}/mini-program-targets"
    rows = request("POST", path, config(), 201)
    assert {r["code"] for r in rows} == {"BRAND_WX", "BRAND_ALIPAY"}
    assert {r["platform"] for r in rows} == {"WECHAT_MINI_PROGRAM", "ALIPAY_MINI_PROGRAM"}
    assert len({r["name"] for r in rows}) == 1
    update_path = f"/systems/mini-program-targets/{rows[0]['id']}"
    members = [{"id": r["id"], "revision": r["revision"]} for r in rows]

    def snapshot():
        with engine.connect() as db:
            return {
                m.__tablename__: [
                    dict(r) for r in db.execute(select(m.__table__).order_by(m.id)).mappings()
                ]
                for m in (ReleaseTarget, OperationLog)
            }

    if scenario == "create_edit":
        body = dict(config(name="Renamed"), members=members)
        body["platforms"][1]["enabled"] = False
        saved = request("PATCH", update_path, body)
        assert {r["id"] for r in saved} == {r["id"] for r in rows}
        assert all(r["revision"] == 2 and r["name"] == "Renamed" for r in saved)
        assert [r["enabled"] for r in saved] == [True, False]
        saved = request(
            "PATCH",
            update_path,
            dict(
                config(name="Renamed"),
                members=[{"id": r["id"], "revision": r["revision"]} for r in saved],
            ),
        )
        assert all(r["enabled"] and r["revision"] == 3 for r in saved)
    elif scenario == "legacy":
        legacy = request(
            "POST",
            f"/systems/{sid}/release-targets",
            dict(code="OLD_WX", name="Old brand", platform="WECHAT_MINI_PROGRAM", app_id="wxold"),
            201,
        )
        upgraded = request(
            "PATCH",
            f"/systems/mini-program-targets/{legacy['id']}",
            dict(
                config(code="OLD", name="Old brand"), members=[{"id": legacy["id"], "revision": 1}]
            ),
        )
        assert upgraded[0]["id"] == legacy["id"] and upgraded[0]["revision"] == 2
        assert len(upgraded) == 2
        other = request(
            "POST",
            f"/systems/{sid}/release-targets",
            dict(
                code="UNRELATED", name="Old brand", platform="ALIPAY_MINI_PROGRAM", app_id="other"
            ),
            201,
        )
        assert other["id"] not in {r["id"] for r in upgraded}
    elif scenario == "conflicts":
        before = snapshot()
        request("POST", path, config(both=False), 409)
        request("PATCH", update_path, dict(config(), members=members[:1]), 409)
        request(
            "PATCH",
            update_path,
            dict(config(), members=[{**m, "revision": 99} for m in members]),
            409,
        )
        request("PATCH", update_path, dict(config(both=False), members=members), 409)
        request(
            "PATCH",
            f"/systems/release-targets/{rows[0]['id']}",
            {"revision": 1, "name": "Split"},
            409,
        )
        request("POST", path, {**config(), "platforms": [config()["platforms"][0]] * 2}, 422)
        partial = config(code="PARTIAL")
        partial["platforms"][1]["app_id"] = None
        request("POST", path, partial, 409)
        assert snapshot() == before
        other_sid = create_test_system(engine)
        request("POST", f"/systems/{other_sid}/mini-program-targets", config(), 201)
    elif scenario == "rollback":
        before = snapshot()
        original = AuditService.log

        def broken(self, *args, **kwargs):
            if len(args) > 2 and args[2].startswith("RELEASE_TARGET_BUNDLE"):
                raise RuntimeError("synthetic audit failure")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(AuditService, "log", broken)
        for target_id, body in [
            (None, config(code="FAILED")),
            (rows[0]["id"], dict(config(name="Failed"), members=members)),
        ]:
            with Session(engine) as db:
                try:
                    payload = (
                        MiniProgramTargetUpdate(**body)
                        if target_id
                        else __import__(
                            "app.schemas.target_release", fromlist=["MiniProgramTargetCreate"]
                        ).MiniProgramTargetCreate(**body)
                    )
                    TargetReleaseService(db).save_mini_program(sid, payload, uid, target_id)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("failure was not raised")
                assert not db.new and not db.dirty
            assert snapshot() == before
    elif scenario == "race":
        barrier = Barrier(2)

        def attempt(label):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    TargetReleaseService(db).save_mini_program(
                        sid,
                        MiniProgramTargetUpdate(**dict(config(name=label), members=members)),
                        uid,
                        rows[0]["id"],
                    )
                    return "ok"
                except Exception as exc:
                    assert getattr(exc, "status_code", None) == 409, repr(exc)
                    return "conflict"

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(attempt, ["winner A", "winner B"]))
        assert sorted(results) == ["conflict", "ok"]
        with Session(engine) as db:
            current = list(db.scalars(select(ReleaseTarget).where(ReleaseTarget.system_id == sid)))
            assert len({r.name for r in current}) == 1 and all(r.revision == 2 for r in current)
    elif scenario == "create_race":
        barrier = Barrier(2)
        from app.schemas.target_release import MiniProgramTargetCreate

        def attempt_create(label):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    TargetReleaseService(db).save_mini_program(
                        sid, MiniProgramTargetCreate(**config(code="RACE", name=label)), uid
                    )
                    return "ok"
                except Exception as exc:
                    assert getattr(exc, "status_code", None) == 409, repr(exc)
                    return "conflict"

        with ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(attempt_create, ["first", "second"]))
        assert sorted(outcomes) == ["conflict", "ok"]
        with Session(engine) as db:
            new = list(
                db.scalars(
                    select(ReleaseTarget).where(ReleaseTarget.code.in_(["RACE_WX", "RACE_ALIPAY"]))
                )
            )
            assert len(new) == 2 and len({r.name for r in new}) == 1
    elif scenario == "membership_change":
        single = request("POST", path, config(code="SINGLE", both=False), 201)[0]
        request(
            "POST",
            f"/systems/{sid}/release-targets",
            dict(
                code="SINGLE_ALIPAY",
                name="Brand",
                platform="ALIPAY_MINI_PROGRAM",
                app_id="2021000000000002",
            ),
            201,
        )
        before = snapshot()
        request(
            "PATCH",
            f"/systems/mini-program-targets/{single['id']}",
            dict(config(code="SINGLE"), members=[{"id": single["id"], "revision": 1}]),
            409,
        )
        assert snapshot() == before
        # Even a brand configured on only one platform reserves its entire prefix.
        request("POST", path, config(code="RESERVED", both=False), 201)
        before = snapshot()
        opposite = dict(config(code="RESERVED"), platforms=[config()["platforms"][1]])
        request("POST", path, opposite, 409)
        assert snapshot() == before
    elif scenario == "permissions":
        with Session(engine) as db:
            user = User(
                username="no-target-permission",
                display_name="No permission",
                password_hash="unused",
                status="ACTIVE",
                must_change_password=False,
            )
            db.add(user)
            db.commit()
            actor = user.id
        auth = {"Authorization": "Bearer " + create_access_token(actor)}
        before = snapshot()
        request("POST", path, config(code="DENIED"), 403, auth)
        request("PATCH", update_path, dict(config(), members=members), 403, auth)
        request("POST", path, config(code="UNAUTH"), 401, {})
        assert snapshot() == before
    elif scenario == "publication":
        with Session(engine) as db:
            version = Version(
                version_no="GROUPED-V1",
                name="Grouped release",
                system_id=sid,
                created_by=uid,
                updated_by=uid,
            )
            db.add(version)
            db.flush()
            req = Requirement(
                requirement_no="GROUPED-REQ",
                title="Grouped requirement",
                requirement_type="FEATURE",
                description="Isolated test",
                system_id=sid,
                status="DONE",
                content_revision=1,
                confirmed_revision=1,
                current_version_id=version.id,
                created_by=uid,
                updated_by=uid,
            )
            db.add(req)
            db.flush()
            db.add(VersionRequirement(version_id=version.id, requirement_id=req.id, added_by=uid))
            db.commit()
            vid = version.id
        wx = next(r for r in rows if r["platform"] == "WECHAT_MINI_PROGRAM")
        ali = next(r for r in rows if r["platform"] == "ALIPAY_MINI_PROGRAM")
        now = datetime.now(UTC)
        published = request(
            "POST",
            f"/versions/{vid}/publish",
            dict(
                revision=1,
                released_at=(now - timedelta(hours=2)).isoformat(),
                release_notes="Published WeChat",
                target_ids=[wx["id"]],
            ),
        )
        original = published["release"]
        with Session(engine) as db:
            notifications = db.scalar(select(func.count()).select_from(Notification))
        options = request("GET", f"/versions/{vid}/release-targets")
        assert next(r for r in options if r["id"] == wx["id"])["covered"]
        assert not next(r for r in options if r["id"] == ali["id"])["covered"]
        version = request("GET", f"/versions/{vid}")
        request(
            "POST",
            f"/versions/{vid}/release-coverage",
            dict(
                version_revision=version["revision"],
                released_at=(now - timedelta(hours=1)).isoformat(),
                target_ids=[ali["id"]],
            ),
            201,
        )
        changed = request("PATCH", update_path, dict(config(name="Renamed later"), members=members))
        assert {r["id"] for r in changed} == {r["id"] for r in rows}
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(Release)) == 1
            assert db.scalar(select(func.count()).select_from(Notification)) == notifications
            records = list(db.scalars(select(ReleaseBatchTarget).order_by(ReleaseBatchTarget.id)))
            assert len(records) == 2 and all(r.name == "Brand" for r in records)
            assert records[0].completed_at != records[1].completed_at
            assert records[0].code == "BRAND_WX" and records[1].code == "BRAND_ALIPAY"
        options = request("GET", "/target-release-records/options")
        assert len(options) == 2
        assert any("微信小程序" in item["label"] for item in options)
        assert any("支付宝小程序" in item["label"] for item in options)
        assert (
            request("GET", f"/releases/{original['id']}")["released_at"] == original["released_at"]
        )

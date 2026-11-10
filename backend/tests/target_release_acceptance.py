"""Release coverage is bookkeeping, never a version-publish gate (PG and MySQL)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from alembic import command
from app.core.exceptions import AppError
from app.models.entities import (
    Feedback,
    Notification,
    OperationLog,
    Permission,
    Release,
    ReleaseBatch,
    ReleaseBatchTarget,
    Requirement,
    RequirementFeedback,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.schemas.target_release import ReleaseCoverageCreate
from app.schemas.version import PublishVersionRequest
from app.services.target_release_service import TargetReleaseService
from app.services.version_service import VersionService

SCENARIOS = [
    "publish_selected",
    "publish_empty",
    "supplement",
    "legacy",
    "legacy_plan",
    "scope",
    "snapshot",
    "rollback",
    "record_rollback",
    "race",
    "publish_race",
    "migration",
    "domains",
    "validation",
    "publish_gate",
    "retired",
    "alipay",
    "alipay_migration",
]


def exercise_targets(fixture, scenario, monkeypatch):
    client, engine, uid, headers = fixture
    system_id = create_test_system(engine)
    base = "/api/v1"

    def request(method, path, body=None, status=200, auth=headers):
        response = client.request(method, base + path, headers=auth, json=body)
        assert response.status_code == status, response.text
        return response.json()

    targets = []
    for code in ["A", "B", "C"]:
        targets.append(
            request(
                "POST",
                f"/systems/{system_id}/release-targets",
                dict(
                    code=code,
                    name=f"小程序{code}",
                    platform=(
                        "ALIPAY_MINI_PROGRAM"
                        if scenario == "alipay" and code == "C"
                        else "PC_WEB"
                        if code == "B"
                        else "WECHAT_MINI_PROGRAM"
                    ),
                    app_id=f"wx{code}",
                ),
                201,
            )
        )
    with Session(engine) as db:
        version = Version(
            version_no="TARGET-V1",
            name="多目标版本",
            system_id=system_id,
            created_by=uid,
            updated_by=uid,
        )
        db.add(version)
        db.flush()
        req = Requirement(
            requirement_no="TARGET-REQ",
            title="多目标需求",
            requirement_type="FEATURE",
            description="隔离验收内容",
            system_id=system_id,
            status="DONE",
            content_revision=1,
            confirmed_revision=1,
            created_by=uid,
            updated_by=uid,
            current_version_id=version.id,
        )
        fb = Feedback(
            feedback_no="TARGET-FB",
            title="原始反馈",
            description="反馈内容",
            feedback_type="OTHER",
            system_id=system_id,
            status="REQUIREMENT_LINKED",
            submitter_id=uid,
            created_by=uid,
            updated_by=uid,
        )
        db.add_all([req, fb])
        db.flush()
        db.add(VersionRequirement(version_id=version.id, requirement_id=req.id, added_by=uid))
        db.add(RequirementFeedback(requirement_id=req.id, feedback_id=fb.id, is_primary=True))
        if engine.dialect.name != "mysql":
            fb.main_requirement_id = req.id
        db.commit()
        vid, rid, fid = version.id, req.id, fb.id
    path = f"/versions/{vid}"

    def version():
        return request("GET", path)

    def batches():
        return request("GET", path + "/release-batches")

    def publish(ids=None, status=200, **extra):
        return request(
            "POST",
            path + "/publish",
            dict(
                revision=version()["revision"],
                released_at=datetime.now(UTC).isoformat(),
                release_notes="正常版本发布",
                target_ids=ids or [],
                **extra,
            ),
            status,
        )

    def record(ids=None, status=201, **extra):
        return request(
            "POST",
            path + "/release-coverage",
            dict(
                version_revision=version()["revision"],
                released_at=datetime.now(UTC).isoformat(),
                target_ids=ids or [targets[2]["id"]],
                notes="实际已发布, 补充记录",
                **extra,
            ),
            status,
        )

    def counts():
        with Session(engine) as db:
            return tuple(
                db.scalar(select(func.count()).select_from(m))
                for m in [Release, Notification, OperationLog, ReleaseBatchTarget]
            )

    def snapshot():
        with engine.connect() as conn:
            return {
                m.__tablename__: [
                    dict(r) for r in conn.execute(select(m.__table__).order_by(m.id)).mappings()
                ]
                for m in [
                    Release,
                    Version,
                    Requirement,
                    Feedback,
                    Notification,
                    OperationLog,
                    ReleaseBatch,
                    ReleaseBatchTarget,
                ]
            }

    first = [targets[0]["id"], targets[1]["id"]]
    if scenario in {"alipay", "alipay_migration"}:
        mysql = engine.dialect.name == "mysql"
        cfg = Config(
            str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
        )
        previous = "mysql57_0015" if mysql else "0017_target_releases"
        if scenario == "alipay_migration":
            # Upgrade existing directory rows and actual-success snapshots without rewrites.
            publish(first)
            before = snapshot()
            directory = request("GET", f"/systems/{system_id}/release-targets")
            command.downgrade(cfg, previous)
            for table in ("sys_release_target", "rd_release_batch_target"):
                with pytest.raises(DBAPIError), engine.begin() as conn:
                    conn.execute(text(f"UPDATE {table} SET platform='ALIPAY_MINI_PROGRAM'"))
            command.upgrade(cfg, "head")
            assert snapshot() == before
            assert request("GET", f"/systems/{system_id}/release-targets") == directory
        for target in (targets[0], targets[2]):
            result = request(
                "PATCH",
                f"/systems/release-targets/{target['id']}",
                dict(
                    revision=target["revision"],
                    platform="ALIPAY_MINI_PROGRAM",
                    app_id="2026000000000001",
                    url=None,
                ),
            )
            assert result["platform"] == "ALIPAY_MINI_PROGRAM"
        with pytest.raises(RuntimeError, match="Alipay target history exists"):
            command.downgrade(cfg, previous)
        if scenario == "alipay":
            publish(first)
        prior_release = snapshot()["rd_release"]
        record([targets[2]["id"]])
        assert counts()[0] == 1 and version()["status"] == "RELEASED"
        assert snapshot()["rd_release"] == prior_release
        records = request("GET", "/target-release-records")["items"]
        alipay = [r for r in records if r["platform"] == "ALIPAY_MINI_PROGRAM"]
        assert len(alipay) == (2 if scenario == "alipay" else 1)
        assert all(r["app_id"] == "2026000000000001" for r in alipay)
        # Changing the directory must not rewrite historical platform/AppID snapshots.
        for target in (targets[0], targets[2]):
            request(
                "PATCH",
                f"/systems/release-targets/{target['id']}",
                dict(revision=2, platform="PC_WEB", app_id=None, url="https://example.org"),
            )
        assert request("GET", "/target-release-records")["items"] == records
        with pytest.raises(RuntimeError, match="Alipay target history exists"):
            command.downgrade(cfg, previous)
        for table in ("sys_release_target", "rd_release_batch_target"):
            with pytest.raises(DBAPIError), engine.begin() as conn:
                conn.execute(text(f"UPDATE {table} SET platform='UNSUPPORTED'"))
        if mysql:
            from app.core.mysql_preflight import validate_mysql

            with engine.connect() as conn:
                assert validate_mysql(conn)["table_count"] == 35
        else:
            command.check(cfg)
        return
    if scenario == "migration":
        # Only directory rows exist: refuse downgrade without dropping history.
        mysql = engine.dialect.name == "mysql"
        cfg = Config(
            str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
        )
        target = "mysql57_0014" if mysql else "0016_announcements"
        with pytest.raises(RuntimeError, match="history exists"):
            command.downgrade(cfg, target)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sys_release_target"))
        command.downgrade(cfg, target)
        with engine.connect() as conn:
            before = dict(conn.execute(text("SELECT * FROM rd_version")).mappings().one())
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            after = dict(conn.execute(text("SELECT * FROM rd_version")).mappings().one())
            assert not after.pop("release_frozen") and after == before
        if mysql:
            from app.core.mysql_preflight import validate_mysql

            with engine.connect() as conn:
                assert validate_mysql(conn)["table_count"] == 35
        else:
            command.check(cfg)
        return
    if scenario == "legacy":
        with Session(engine) as db:
            ver = db.get(Version, vid)
            ver.status = "RELEASED"
            ver.system_id = None
            db.get(Requirement, rid).status = "ONLINE"
            db.add(
                Release(
                    version_id=vid,
                    created_by=uid,
                    updated_by=uid,
                    released_at=datetime.now(UTC),
                    release_notes="历史发布",
                    result="SUCCESS",
                )
            )
            db.commit()
        before = snapshot()
        assert batches()["legacy_unrecorded"] and batches()["coverage_count"] == 0
        record(status=409)
        record(system_id=system_id)
        assert version()["system_id"] is None
        after = snapshot()
        for model in [Release, Requirement, Feedback, Notification]:
            assert after[model.__tablename__] == before[model.__tablename__]
        other = create_test_system(engine)
        record(first, status=409, system_id=other)
        return
    if scenario == "legacy_plan":
        with Session(engine) as db:
            ver = db.get(Version, vid)
            ver.release_frozen = True
            b = ReleaseBatch(
                version_id=vid,
                system_id=system_id,
                kind="INITIAL",
                status="IN_PROGRESS",
                release_notes="旧计划",
                created_by=uid,
                updated_by=uid,
            )
            db.add(b)
            db.flush()
            for index, t in enumerate(targets[:2]):
                db.add(
                    ReleaseBatchTarget(
                        batch_id=b.id,
                        target_id=t["id"],
                        name=t["name"],
                        code=t["code"],
                        platform=t["platform"],
                        active=True,
                        completed_at=datetime.now(UTC) if index == 0 else None,
                        recorded_at=datetime.now(UTC) if index == 0 else None,
                        completed_by=uid if index == 0 else None,
                        operator_name="历史登记人" if index == 0 else None,
                        created_by=uid,
                        updated_by=uid,
                    )
                )
            db.commit()
            bid = b.id
        before = snapshot()
        # An incomplete legacy plan cannot block normal publication or infer B as released.
        publish()
        assert version()["status"] == "RELEASED" and batches()["coverage_count"] == 1
        history = next(b for b in batches()["items"] if b["id"] == bid)
        assert history["status"] == "CANCELED" and not history["targets"][1]["active"]
        assert (
            snapshot()[ReleaseBatchTarget.__tablename__][0]
            == before[ReleaseBatchTarget.__tablename__][0]
        )
        record([targets[1]["id"]])
        assert batches()["coverage_count"] == 2 and counts()[0] == 1
        return
    if scenario == "retired":
        before = snapshot()
        request(
            "POST",
            path + "/release-batches",
            dict(
                version_revision=1, kind="INITIAL", target_ids=first, release_notes="旧客户端计划"
            ),
            409,
        )
        request(
            "POST",
            path + "/release-batches/1/targets/1/complete",
            dict(
                version_revision=1,
                batch_revision=1,
                revision=1,
                released_at=datetime.now(UTC).isoformat(),
            ),
            409,
        )
        request(
            "PATCH",
            path + "/release-batches/1/targets",
            dict(version_revision=1, revision=1, target_ids=first, reason="旧客户端调整"),
            409,
        )
        request(
            "POST",
            path + "/release-batches/1/cancel",
            dict(version_revision=1, revision=1, reason="旧客户端取消"),
            409,
        )
        publish(status=409, initial_batch_id=1, batch_revision=1)
        assert snapshot() == before
        return
    if scenario == "publish_gate":
        with Session(engine) as db:
            db.get(Requirement, rid).status = "TESTING"
            db.commit()
        before = snapshot()
        publish(first, status=409)
        record(first, status=409)
        assert snapshot() == before
        return
    if scenario in {"rollback", "record_rollback"}:
        if scenario == "record_rollback":
            publish()
        before = snapshot()
        original = TargetReleaseService.append_coverage

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected after coverage rows and audit")

        with monkeypatch.context() as patch:
            patch.setattr(TargetReleaseService, "append_coverage", fail)
            with Session(engine) as db, pytest.raises(RuntimeError, match="injected"):
                if scenario == "rollback":
                    VersionService(db).publish(
                        vid,
                        PublishVersionRequest(
                            revision=version()["revision"],
                            released_at=datetime.now(UTC).isoformat(),
                            release_notes="事务验证",
                            target_ids=first,
                        ),
                        uid,
                    )
                else:
                    TargetReleaseService(db).record_coverage(
                        vid,
                        ReleaseCoverageCreate(
                            version_revision=version()["revision"],
                            target_ids=first,
                            released_at=datetime.now(UTC).isoformat(),
                        ),
                        uid,
                    )
        assert snapshot() == before
        return
    if scenario in {"race", "publish_race"}:
        if scenario == "race":
            publish()
        barrier = Barrier(2)
        rev = version()["revision"]

        def run():
            with Session(engine) as db:
                barrier.wait(timeout=15)
                try:
                    if scenario == "race":
                        TargetReleaseService(db).record_coverage(
                            vid,
                            ReleaseCoverageCreate(
                                version_revision=rev,
                                target_ids=first,
                                released_at=datetime.now(UTC).isoformat(),
                            ),
                            uid,
                        )
                    else:
                        VersionService(db).publish(
                            vid,
                            PublishVersionRequest(
                                revision=rev,
                                target_ids=first,
                                released_at=datetime.now(UTC).isoformat(),
                                release_notes="并发发布",
                            ),
                            uid,
                        )
                    return "ok"
                except AppError:
                    return "blocked"

        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(run), pool.submit(run)
            assert sorted([a.result(timeout=25), b.result(timeout=25)]) == ["blocked", "ok"]
        assert counts()[0] == 1 and batches()["coverage_count"] == 2
        return
    if scenario == "validation":
        record(first, status=409)
        publish([first[0], first[0]], status=422)
        other = create_test_system(engine)
        foreign = request(
            "POST",
            f"/systems/{other}/release-targets",
            dict(code="X", name="其他系统PC", platform="PC_WEB"),
            201,
        )
        before = snapshot()
        publish([foreign["id"]], status=409)
        assert snapshot() == before
        publish()
        before = snapshot()
        for ids, status in [
            ([foreign["id"]], 409),
            ([first[0]] * 2, 422),
            (list(range(1, 52)), 422),
        ]:
            record(ids, status=status)
        request(
            "POST",
            path + "/release-coverage",
            dict(
                version_revision=version()["revision"],
                target_ids=[],
                released_at=datetime.now(UTC).isoformat(),
            ),
            422,
        )
        request(
            "POST",
            path + "/release-coverage",
            dict(
                version_revision=version()["revision"],
                target_ids=first,
                released_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
            ),
            422,
        )
        request(
            "POST",
            path + "/release-coverage",
            dict(
                version_revision=version()["revision"],
                target_ids=first,
                released_at="2026-11-01T12:00:00",
            ),
            422,
        )
        assert snapshot() == before
        return
    publish([] if scenario == "publish_empty" else first)
    assert version()["status"] == "RELEASED" and not version()["release_frozen"]
    assert request("GET", f"/requirements/{rid}")["status"] == "ONLINE"
    assert request("GET", f"/feedbacks/{fid}")["status"] == "ONLINE"
    assert counts()[0] == 1
    if scenario == "publish_empty":
        assert batches()["coverage_count"] == 0 and batches()["items"] == []
        record(first)
        assert batches()["coverage_count"] == 2
        return
    assert batches()["coverage_count"] == 2  # C remains unselected, version still online.
    if scenario == "scope":
        from app.core.security import create_access_token

        with Session(engine) as db:
            user = User(
                username="target-outsider",
                display_name="范围外用户",
                password_hash="unused",
                must_change_password=False,
            )
            role = Role(code="TARGET_SELF", name="仅本人目标", data_scope="SELF")
            db.add_all([user, role])
            db.flush()
            for permission in db.scalars(
                select(Permission).where(
                    Permission.code.in_(
                        [
                            "rd.version.view",
                            "rd.release.view",
                            "rd.version.publish",
                            "sys.system.manage",
                        ]
                    )
                )
            ):
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            db.add(UserRole(user_id=user.id, role_id=role.id))
            db.commit()
            own = {"Authorization": "Bearer " + create_access_token(user.id)}
        request("GET", path + "/release-batches", status=404, auth=own)
        request("GET", path + "/release-targets", status=404, auth=own)
        request("GET", f"/systems/{system_id}/release-targets", status=403, auth=own)
        body = dict(
            version_revision=version()["revision"],
            target_ids=[targets[2]["id"]],
            released_at=datetime.now(UTC).isoformat(),
        )
        request("POST", path + "/release-coverage", body, 404, auth=own)
        assert request("GET", "/target-release-records", auth=own)["total"] == 0
        assert request("GET", "/target-release-records/options", auth=own) == []
        request("POST", path + "/release-coverage", body, 401, auth={})
        with Session(engine) as db:
            role = db.scalar(select(Role).where(Role.code == "TARGET_SELF"))
            perm = db.scalar(select(Permission).where(Permission.code == "rd.version.publish"))
            db.delete(db.get(RolePermission, (role.id, perm.id)))
            db.commit()
        request("POST", path + "/release-coverage", body, 403, auth=own)
        return
    if scenario == "snapshot":
        t = targets[0]
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"], name="目录已改名", enabled=False),
        )
        assert batches()["items"][0]["targets"][0]["name"] == "小程序A"
        t = targets[2]
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"], enabled=False),
        )
        record(status=409)
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"], name="旧修订"),
            409,
        )
        request(
            "POST",
            f"/systems/{system_id}/release-targets",
            dict(code="B", name="重复编码", platform="PC_WEB"),
            409,
        )
        return
    if scenario == "domains":
        with engine.begin() as conn:
            conn.execute(text("UPDATE rd_version SET release_frozen=true"))
        with engine.connect() as conn:
            for sql in [
                "UPDATE rd_release_batch_target SET notes='rewrite' WHERE completed_at IS NOT NULL",
                "DELETE FROM rd_release_batch_target WHERE completed_at IS NOT NULL",
                "UPDATE rd_version SET release_frozen=false",
                "UPDATE sys_release_target SET platform='INVALID'",
                "UPDATE rd_release_batch SET kind='INVALID'",
            ]:
                with pytest.raises(DBAPIError):
                    conn.execute(text(sql))
                conn.rollback()
        return
    before = snapshot()
    rev = version()["revision"]
    record(first, status=409)  # Covered targets cannot silently become new releases.
    assert snapshot() == before
    record()
    after = snapshot()
    for model in [Release, Requirement, Feedback, Notification]:
        assert after[model.__tablename__] == before[model.__tablename__]
    assert batches()["coverage_count"] == 3
    assert (
        after[Version.__tablename__][0]["released_at"]
        == before[Version.__tablename__][0]["released_at"]
    )
    request(
        "POST",
        path + "/release-coverage",
        dict(
            version_revision=rev,
            target_ids=[targets[2]["id"]],
            released_at=datetime.now(UTC).isoformat(),
        ),
        409,
    )
    assert request("GET", "/target-release-records")["total"] == 3
    assert request("GET", f"/target-release-records?target_id={targets[2]['id']}")["total"] == 1
    assert len(request("GET", "/target-release-records/options")) == 3

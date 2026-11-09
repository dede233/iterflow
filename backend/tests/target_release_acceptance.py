"""Target publishing invariants, shared by task-isolated PostgreSQL and MySQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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
from app.schemas.target_release import ReleaseTargetComplete
from app.services.target_release_service import TargetReleaseService
from app.services.version_service import VersionService

SCENARIOS = [
    "initial",
    "supplement",
    "adjust",
    "cancel",
    "snapshot",
    "rollback",
    "race",
    "migration",
    "domains",
    "legacy",
    "scope",
    "traditional",
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
                    platform="WECHAT_MINI_PROGRAM",
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

    def create(kind="INITIAL", ids=None, reason=None):
        return request(
            "POST",
            path + "/release-batches",
            dict(
                version_revision=version()["revision"],
                kind=kind,
                target_ids=ids or [t["id"] for t in targets[:2]],
                release_notes="本批发布说明",
                reason=reason,
            ),
            201,
        )

    def complete(batch, index=0, status=200):
        row = batch["targets"][index]
        return request(
            "POST",
            path + f"/release-batches/{batch['id']}/targets/{row['id']}/complete",
            dict(
                version_revision=version()["revision"],
                batch_revision=batch["revision"],
                revision=row["revision"],
                released_at=datetime.now(UTC).isoformat(),
                notes="外部平台已实际完成",
            ),
            status,
        )

    def counts():
        with Session(engine) as db:
            return tuple(
                db.scalar(select(func.count()).select_from(m))
                for m in [Release, Notification, OperationLog, ReleaseBatchTarget]
            )

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
    if scenario == "scope":
        visible_batch = create()
        visible_batch = complete(visible_batch)
        complete(visible_batch, 1)
        assert request("GET", "/target-release-records")["total"] == 2
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
            codes = ["rd.version.view", "rd.release.view", "sys.system.manage"]
            for permission in db.scalars(select(Permission).where(Permission.code.in_(codes))):
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            db.add(UserRole(user_id=user.id, role_id=role.id))
            db.commit()
            own = {"Authorization": "Bearer " + create_access_token(user.id)}
        request("GET", path + "/release-batches", status=404, auth=own)
        request("GET", path + "/release-targets", status=404, auth=own)
        request("GET", f"/systems/{system_id}/release-targets", status=403, auth=own)
        request(
            "POST",
            path + "/release-batches",
            dict(
                version_revision=1,
                kind="INITIAL",
                target_ids=[targets[0]["id"]],
                release_notes="无权限发布",
            ),
            403,
            auth=own,
        )
        assert request("GET", "/target-release-records", auth=own)["total"] == 0
        assert request("GET", "/target-release-records/options", auth=own) == []
        request("GET", path + "/release-batches", status=401, auth={})
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
                    release_notes="历史发布记录",
                    result="SUCCESS",
                )
            )
            db.commit()
            original = dict(db.execute(select(Release.__table__)).mappings().one())
        assert batches()["legacy_unrecorded"] and batches()["coverage_count"] == 0
        body = dict(
            version_revision=version()["revision"],
            kind="SUPPLEMENT",
            target_ids=[targets[0]["id"]],
            release_notes="历史版本补发",
        )
        request("POST", path + "/release-batches", body, 409)
        body["system_id"] = system_id
        batch = request("POST", path + "/release-batches", body, 201)
        complete(batch)
        assert version()["system_id"] is None and batches()["coverage_count"] == 1
        with Session(engine) as db:
            assert dict(db.execute(select(Release.__table__)).mappings().one()) == original
        return
    if scenario == "traditional":
        body = dict(
            revision=version()["revision"],
            released_at=datetime.now(UTC).isoformat(),
            release_notes="传统单次发布",
        )
        request("POST", path + "/publish", body, 409)
        body.update(legacy_single=True, legacy_reason="无需单独记账的传统发布")
        request("POST", path + "/publish", body)
        assert (
            counts()[0] == 1 and batches()["legacy_unrecorded"] and batches()["coverage_count"] == 0
        )
        return
    batch = create()
    assert not batches()["release_frozen"] and batch["total"] == 2
    if scenario == "cancel":
        request(
            "POST",
            path + f"/release-batches/{batch['id']}/cancel",
            dict(
                version_revision=version()["revision"],
                revision=batch["revision"],
                reason="本次取消",
            ),
        )
        assert create()["id"] != batch["id"]
        return
    if scenario == "race":
        barrier = Barrier(2)
        vrev = version()["revision"]

        def run():
            with Session(engine) as db:
                barrier.wait(timeout=15)
                try:
                    row = batch["targets"][0]
                    TargetReleaseService(db).complete(
                        vid,
                        batch["id"],
                        row["id"],
                        ReleaseTargetComplete(
                            version_revision=vrev,
                            batch_revision=batch["revision"],
                            revision=row["revision"],
                            released_at=datetime.now(UTC).isoformat(),
                        ),
                        uid,
                    )
                    return "ok"
                except AppError:
                    return "blocked"

        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(run), pool.submit(run)
            assert sorted([a.result(timeout=25), b.result(timeout=25)]) == ["blocked", "ok"]
        batch = batches()["items"][0]
        assert batch["completed"] == 1 and counts()[0] == 0
        # Last success racing itself must produce exactly one global Release.
        barrier = Barrier(2)
        vrev = version()["revision"]

        def last():
            with Session(engine) as db:
                barrier.wait(timeout=15)
                try:
                    row = batch["targets"][1]
                    TargetReleaseService(db).complete(
                        vid,
                        batch["id"],
                        row["id"],
                        ReleaseTargetComplete(
                            version_revision=vrev,
                            batch_revision=batch["revision"],
                            revision=row["revision"],
                            released_at=datetime.now(UTC).isoformat(),
                        ),
                        uid,
                    )
                    return "ok"
                except AppError:
                    return "blocked"

        with ThreadPoolExecutor(2) as pool:
            a, b = pool.submit(last), pool.submit(last)
            assert sorted([a.result(timeout=25), b.result(timeout=25)]) == ["blocked", "ok"]
        assert counts()[0] == 1 and version()["status"] == "RELEASED"
        return
    if scenario == "snapshot":
        t = targets[0]
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"], name="目录已改名"),
        )
        assert batches()["items"][0]["targets"][0]["name"] == "小程序A"
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"] + 1, enabled=False),
        )
        complete(batch, 0, status=409)
        assert counts()[0] == 0 and batches()["items"][0]["completed"] == 0
        request(
            "PATCH",
            f"/systems/release-targets/{t['id']}",
            dict(revision=t["revision"], name="旧修订"),
            409,
        )
        request(
            "POST",
            f"/systems/{system_id}/release-targets",
            dict(code="B", name="重复", platform="PC_WEB"),
            409,
        )
        request(
            "POST",
            path + "/release-batches",
            dict(
                version_revision=version()["revision"],
                kind="INITIAL",
                target_ids=[targets[1]["id"]] * 2,
                release_notes="重复目标",
            ),
            422,
        )
        return
    batch = complete(batch)
    assert batches()["release_frozen"] and batch["completed"] == 1
    assert version()["status"] == "READY" and counts()[0] == 0
    assert request("GET", f"/requirements/{rid}")["release_frozen"]
    if scenario == "adjust":
        body = dict(
            version_revision=version()["revision"],
            revision=batch["revision"],
            target_ids=[targets[1]["id"]],
            reason="移除已完成",
        )
        request("PATCH", path + f"/release-batches/{batch['id']}/targets", body, 409)
        body.update(target_ids=[targets[0]["id"]], reason="另一个目标取消")
        batch = request("PATCH", path + f"/release-batches/{batch['id']}/targets", body)
        assert counts()[0] == 0 and batch["completed"] == batch["total"] == 1
        request(
            "POST",
            path + "/publish",
            dict(
                revision=version()["revision"],
                initial_batch_id=batch["id"],
                batch_revision=batch["revision"],
                released_at=datetime.now(UTC).isoformat(),
                release_notes="确认整体上线",
            ),
        )
        assert version()["status"] == "RELEASED"
        return
    if scenario == "rollback":
        original = VersionService._publish

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected transaction failure after all side effects")

        before = counts()
        with monkeypatch.context() as patch:
            patch.setattr(VersionService, "_publish", fail)
            with Session(engine) as db:
                row = batch["targets"][1]
                with pytest.raises(RuntimeError, match="injected"):
                    TargetReleaseService(db).complete(
                        vid,
                        batch["id"],
                        row["id"],
                        ReleaseTargetComplete(
                            version_revision=version()["revision"],
                            batch_revision=batch["revision"],
                            revision=row["revision"],
                            released_at=datetime.now(UTC).isoformat(),
                        ),
                        uid,
                    )
        assert (
            counts() == before
            and batches()["items"][0]["completed"] == 1
            and version()["status"] == "READY"
        )
        return
    if scenario == "domains":
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
    # The partial freeze also blocks old endpoints and direct single-release bypass.
    request("PATCH", f"/requirements/{rid}", dict(revision=1, title="修改内容"), 409)
    request(
        "PUT",
        f"/requirements/{rid}/participants",
        dict(revision=1, participants=[dict(user_id=uid, role="DEVELOP")]),
        409,
    )
    request(
        "POST",
        f"/requirements/{rid}/workflow",
        dict(revision=1, action="REQUEST_CHANGES", reason="不能改变内容确认"),
        409,
    )
    request(
        "DELETE",
        path + f"/requirements/{rid}",
        dict(revision=1, version_revision=version()["revision"], reason="不能移出清单"),
        409,
    )
    request(
        "PATCH",
        path + "/status",
        dict(revision=version()["revision"], status="CANCELED", reason="不能取消部分实际发布"),
        409,
    )
    request(
        "POST",
        path + "/publish",
        dict(
            revision=version()["revision"],
            released_at=datetime.now(UTC).isoformat(),
            release_notes="不能绕过",
            legacy_single=True,
            legacy_reason="明确单次",
        ),
        409,
    )
    request(
        "POST",
        path + f"/release-batches/{batch['id']}/cancel",
        dict(version_revision=version()["revision"], revision=batch["revision"], reason="不能取消"),
        409,
    )
    request("PATCH", path, dict(revision=version()["revision"], description="修改发布内容"), 409)
    batch = complete(batch, 1)
    assert batch["status"] == "COMPLETED" and version()["status"] == "RELEASED"
    assert request("GET", f"/requirements/{rid}")["status"] == "ONLINE"
    assert request("GET", f"/feedbacks/{fid}")["status"] == "ONLINE"
    assert counts()[0] == 1 and request("GET", "/target-release-records")["total"] == 2
    if scenario == "initial":
        before = counts()
        complete(batch, 1, status=409)
        assert counts() == before
        return
    # Later additions do not change the original release or send global notifications.
    with Session(engine) as db:
        release_before = dict(db.execute(select(Release.__table__)).mappings().one())
    before = counts()
    supplement = create("SUPPLEMENT", [targets[2]["id"]])
    supplement = complete(supplement)
    assert supplement["status"] == "COMPLETED" and batches()["coverage_count"] == 3
    assert counts()[0:2] == before[0:2]
    republish = create("REPUBLISH", [targets[0]["id"]], "外部回滚后重发")
    complete(republish)
    assert counts()[0:2] == before[0:2]
    with Session(engine) as db:
        assert dict(db.execute(select(Release.__table__)).mappings().one()) == release_before
    assert request("GET", "/target-release-records")["total"] == 4
    assert len(request("GET", "/target-release-records/options")) == 3

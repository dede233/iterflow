from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from system_binding_fixture import create_test_system

from alembic import command
from app.core.security import create_access_token
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    FeedbackRecipient,
    OperationLog,
    Permission,
    Release,
    Requirement,
    RequirementFeedback,
    RequirementOnlineFeedback,
    RequirementStep,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope


def _user(engine, name, scope, *codes):
    with Session(engine) as db:
        role = Role(code=name.upper(), name=name, data_scope=scope)
        user = User(username=name, display_name=name, password_hash="unused")
        db.add_all([role, user])
        db.flush()
        user.must_change_password = False
        permissions = list(db.scalars(select(Permission).where(Permission.code.in_(codes))))
        assert len(permissions) == len(codes)
        db.add_all([RolePermission(role_id=role.id, permission_id=perm.id) for perm in permissions])
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _ready_version(engine, creator):
    system = create_test_system(engine)
    with Session(engine) as db:
        version = Version(version_no="ONLINE-1", name="上线版本", system_id=system)
        db.add(version)
        db.flush()
        req = Requirement(
            requirement_no="ONLINE-REQ",
            title="需要线上确认的需求",
            requirement_type="FEATURE",
            description="已验收内容",
            system_id=system,
            status="DONE",
            confirmed_revision=1,
            created_by=creator,
            updated_by=creator,
            current_version_id=version.id,
        )
        source = Feedback(
            feedback_no="ORIGINAL-FB",
            title="原始反馈",
            feedback_type="SYSTEM_ISSUE",
            description="原反馈正文",
            status="REQUIREMENT_LINKED",
            submitter_id=creator,
        )
        db.add_all([req, source])
        db.flush()
        db.add_all(
            [
                VersionRequirement(version_id=version.id, requirement_id=req.id),
                RequirementFeedback(requirement_id=req.id, feedback_id=source.id, is_primary=True),
            ]
        )
        if engine.dialect.name != "mysql":
            source.main_requirement_id = req.id
        db.commit()
        return version.id, req.id, source.id


def exercise_online_review(fixture):
    client, engine, uid, admin_headers = fixture
    author, author_headers = _user(
        engine,
        "online-author",
        DataScope.SELF,
        "rd.requirement.view",
        "rd.feedback.create",
        "rd.feedback.view",
    )
    _, blind_headers = _user(
        engine, "online-submit-only", DataScope.ALL, "rd.requirement.view", "rd.feedback.create"
    )
    _, no_scope_headers = _user(
        engine, "online-outside-scope", DataScope.SELF, "rd.requirement.view", "rd.feedback.create"
    )
    _, read_headers = _user(engine, "online-read", DataScope.ALL, "rd.requirement.view")
    vid, rid, original = _ready_version(engine, author)
    req_path = f"/api/v1/requirements/{rid}"
    review_path = req_path + "/online-review"
    feedback_body = {
        "revision": 1,
        "title": "线上问题",
        "description": "上线后观察到的问题",
        "feedback_type": "SYSTEM_ISSUE",
        "recipient_ids": [uid],
    }

    def request(method, path, headers, body=None, status=200):
        response = client.request(method, path, headers=headers, json=body)
        assert response.status_code == status, response.text
        return response.json()

    assert request("GET", review_path, author_headers, status=409)["code"] == 40987
    request("POST", review_path + "/confirm", author_headers, {"revision": 1}, 409)
    request("POST", review_path + "/feedbacks", author_headers, feedback_body, 409)
    # An isolated inconsistent status cannot authorize reviews without a real Release.
    with engine.begin() as db:
        db.execute(text("UPDATE rd_requirement SET status='ONLINE' WHERE id=:id"), {"id": rid})
    request("GET", review_path, author_headers, status=409)
    with engine.begin() as db:
        db.execute(text("UPDATE rd_requirement SET status='DONE' WHERE id=:id"), {"id": rid})
    published = request(
        "POST",
        f"/api/v1/versions/{vid}/publish",
        admin_headers,
        {"revision": 1, "released_at": datetime.now(UTC).isoformat(), "release_notes": "批准上线"},
    )
    assert published["online_feedback_ids"] == [original]
    release = published["release"]
    current = request("GET", review_path, author_headers)
    assert current == {
        "revision": 2,
        "can_confirm": True,
        "confirmation": None,
        "feedbacks": [],
        "feedback_total": 0,
    }
    request("GET", review_path, no_scope_headers, status=404)
    request("POST", review_path + "/feedbacks", no_scope_headers, feedback_body, 404)
    request("POST", review_path + "/feedbacks", read_headers, feedback_body, 403)
    request("POST", review_path + "/confirm", admin_headers, {"revision": 2}, 403)
    assert (
        request("POST", review_path + "/feedbacks", author_headers, feedback_body, 409)["code"]
        == 40910
    )
    invalid_feedback = {**feedback_body, "revision": 2, "recipient_ids": [99999]}
    request("POST", review_path + "/feedbacks", author_headers, invalid_feedback, 422)
    request("POST", review_path + "/confirm", author_headers, {"revision": 2, "note": "\0"}, 422)
    assert request("GET", review_path, author_headers)["revision"] == 2

    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=10)
        return client.post(
            review_path + "/confirm",
            headers=author_headers,
            json={"revision": 2, "note": "已验证生产效果"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: confirm(), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        next(response.json() for response in responses if response.status_code == 409)["code"]
        == 40910
    )
    confirmed = next(response.json() for response in responses if response.status_code == 200)
    assert confirmed["confirmed_by"] == author and confirmed["note"] == "已验证生产效果"
    assert datetime.fromisoformat(confirmed["confirmed_at"]) >= datetime.fromisoformat(
        release["released_at"]
    )
    with Session(engine) as db:
        db.get(User, author).display_name = "修改后的名字"
        db.commit()
    assert request("GET", review_path, admin_headers)["confirmation"] == confirmed
    assert (
        request("POST", review_path + "/confirm", author_headers, {"revision": 3}, 409)["code"]
        == 40988
    )

    private = request(
        "POST", review_path + "/feedbacks", blind_headers, {**feedback_body, "revision": 3}
    )
    assert private["status"] == "NEW" and private["main_requirement_id"] is None
    assert request("GET", review_path, blind_headers)["feedback_total"] == 0
    assert request("GET", review_path, read_headers)["feedbacks"] == []
    assert request("GET", review_path, author_headers)["feedback_total"] == 0
    for revision in range(4, 14):
        request(
            "POST",
            review_path + "/feedbacks",
            author_headers,
            {**feedback_body, "revision": revision},
        )
    first = request("GET", review_path, admin_headers)
    second = request("GET", review_path + "?page=2", admin_headers)
    assert first["feedback_total"] == second["feedback_total"] == 11
    assert len(first["feedbacks"]) == 10 and [row["id"] for row in second["feedbacks"]] == [
        private["id"]
    ]
    assert request("GET", review_path + "?page=2", author_headers)["feedbacks"] == []
    assert request("GET", review_path, author_headers)["feedback_total"] == 10
    assert [
        row["feedback_id"] for row in request("GET", req_path + "/feedbacks", admin_headers)
    ] == [original]
    assert request("GET", f"/api/v1/releases/{release['id']}", admin_headers) == release

    feedback_path = f"/api/v1/feedbacks/{private['id']}"
    request("DELETE", feedback_path, admin_headers, {"revision": 1, "reason": "测试删除"}, 409)
    reattach = {
        "type": "LINK_EXISTING",
        "requirement_id": rid,
        "revision": 1,
        "accept_on_convert": True,
    }
    assert (
        request("POST", feedback_path + "/accept-and-convert", admin_headers, reattach, 409)["code"]
        == 40989
    )
    with Session(engine) as db:
        db_req = db.get(Requirement, rid)
        assert db_req.status == "ONLINE" and db_req.revision == 14
        assert db.get(Feedback, original).status == "ONLINE"
        assert db.get(Feedback, private["id"]).status == "NEW"
        assert db.get(FeedbackRecipient, (private["id"], uid)).active
        assert db.get(RequirementOnlineFeedback, private["id"]).requirement_id == rid
        assert db.scalar(select(func.count(RequirementFeedback.id))) == 1
        assert db.scalar(select(func.count(Release.id))) == 1
        step = db.scalar(select(RequirementStep).where(RequirementStep.requirement_id == rid))
        assert step.action == "ONLINE_EFFECT_CONFIRMED" and step.actor_id == author
        assert step.detail == {
            "actor_name": confirmed["confirmed_by_name"],
            "note": confirmed["note"],
        }
        record = db.scalar(
            select(OperationLog).where(OperationLog.action == "ONLINE_EFFECT_CONFIRMED")
        )
        assert record.operator_id == author and record.entity_id == rid
        assert (
            db.scalar(
                select(func.count(OperationLog.id)).where(
                    OperationLog.action == "CREATE_ONLINE_FEEDBACK"
                )
            )
            == 11
        )
        assert (
            db.scalar(
                select(func.count(CollaborationEvent.id)).where(
                    CollaborationEvent.action == "RECIPIENT_ADDED"
                )
            )
            == 11
        )

    repair = request(
        "POST",
        feedback_path + "/accept-and-convert",
        admin_headers,
        {
            "type": "CREATE_NEW",
            "revision": 1,
            "accept_on_convert": True,
            "requirement_title": "处理线上反馈",
            "requirement_type": "BUG_FIX",
            "description": "修复线上发现的问题",
            "participants": [{"user_id": uid, "role": "CONFIRM"}],
        },
    )
    assert repair["id"] != rid and repair["status"] == "DRAFT"
    repaired_feedback = request("GET", feedback_path, admin_headers)
    assert repaired_feedback["main_requirement_id"] == repair["id"]
    origin_feedback = request("GET", review_path + "?page=2", admin_headers)["feedbacks"][0]
    assert (
        origin_feedback["id"] == private["id"] and origin_feedback["status"] == "REQUIREMENT_LINKED"
    )


def exercise_online_review_migration(fixture):
    client, engine, uid, headers = fixture
    vid, rid, fid = _ready_version(engine, uid)
    response = client.post(
        f"/api/v1/versions/{vid}/publish",
        headers=headers,
        json={
            "revision": 1,
            "released_at": datetime.now(UTC).isoformat(),
            "release_notes": "批准上线",
        },
    )
    assert response.status_code == 200, response.text
    release_id = response.json()["release"]["id"]
    mysql = engine.dialect.name == "mysql"
    path = "alembic-mysql.ini" if mysql else "alembic.ini"
    cfg = Config(str(Path(__file__).resolve().parents[1] / path))
    previous = "mysql57_0016" if mysql else "0018_alipay_targets"
    head = "mysql57_0029" if mysql else "0031_production_version_deletion"
    table = RequirementOnlineFeedback.__tablename__
    command.downgrade(cfg, previous)
    assert table not in inspect(engine).get_table_names()
    command.upgrade(cfg, "head")
    review = client.get(f"/api/v1/requirements/{rid}/online-review", headers=headers)
    assert review.status_code == 200, review.text
    assert review.json()["can_confirm"] and review.json()["confirmation"] is None
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(RequirementOnlineFeedback)) == 0
        assert db.get(Requirement, rid).status == "ONLINE"
        assert db.get(Feedback, fid).status == "ONLINE"
        assert db.get(Release, release_id).result == "SUCCESS"
        assert db.scalar(select(func.count()).select_from(RequirementStep)) == 0
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head
        db.add(RequirementOnlineFeedback(feedback_id=fid, requirement_id=rid))
        db.commit()
    for values in [
        {"feedback_id": fid, "requirement_id": rid},
        {"feedback_id": 0, "requirement_id": rid},
    ]:
        with pytest.raises(IntegrityError), Session(engine) as db:
            db.add(RequirementOnlineFeedback(**values))
            db.commit()
    with pytest.raises(RuntimeError, match="Online feedback history exists"):
        command.downgrade(cfg, previous)
    with Session(engine) as db:
        expected_head = "mysql57_0017" if mysql else head
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
        assert db.get(RequirementOnlineFeedback, fid).requirement_id == rid

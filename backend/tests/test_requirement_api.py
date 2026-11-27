from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from conftest import assert_revision_conflict, resolve_openapi_ref
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    AttachmentRelation,
    BusinessModule,
    BusinessSystem,
    CollaborationEvent,
    Feedback,
    FeedbackRecipient,
    FileObject,
    OperationLog,
    Permission,
    ReleaseBatch,
    ReleaseBatchTarget,
    ReleaseTarget,
    Requirement,
    RequirementFeedback,
    RequirementOnlineFeedback,
    RequirementParticipant,
    RequirementStep,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import DataScope, UserStatus

SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"

PERMS = {
    "rd.requirement.view",
    "rd.requirement.create",
    "rd.requirement.edit",
    "rd.requirement.status",
    "rd.feedback.view",
    "rd.feedback.create",
    "rd.feedback.edit",
    "rd.feedback.convert",
}

Fixture = tuple[TestClient, Session, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def req_api(tmp_path: Path) -> Iterator[Fixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'req-api.db'}", connect_args={"check_same_thread": False}
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        OperationLog.__table__,
        BusinessSystem.__table__,
        BusinessModule.__table__,
        Feedback.__table__,
        FeedbackRecipient.__table__,
        CollaborationEvent.__table__,
        Version.__table__,
        ReleaseTarget.__table__,
        ReleaseBatch.__table__,
        ReleaseBatchTarget.__table__,
        Requirement.__table__,
        RequirementStep.__table__,
        RequirementParticipant.__table__,
        RequirementFeedback.__table__,
        RequirementOnlineFeedback.__table__,
        FileObject.__table__,
        AttachmentRelation.__table__,
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
        RequirementFeedback,
        FileObject,
        AttachmentRelation,
    ):
        counter = iter(range(1, 100000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        role_all = Role(code="ALLROLE", name="全域", data_scope=DataScope.ALL)
        role_self = Role(code="SELFROLE", name="本人", data_scope=DataScope.SELF)
        requirement_reader_role = Role(
            code="REQUIREMENT_READER", name="仅需求查看", data_scope=DataScope.ALL
        )
        converter_role = Role(code="CONVERTER", name="仅反馈转换", data_scope=DataScope.ALL)
        perms = {code: Permission(code=code, name=code) for code in sorted(PERMS)}
        session.add_all(
            [role_all, role_self, requirement_reader_role, converter_role, *perms.values()]
        )
        session.flush()
        for role in (role_all, role_self):
            for perm in perms.values():
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        session.add(
            RolePermission(
                role_id=requirement_reader_role.id,
                permission_id=perms["rd.requirement.view"].id,
            )
        )
        session.add(
            RolePermission(
                role_id=converter_role.id,
                permission_id=perms["rd.feedback.convert"].id,
            )
        )

        def user(name: str) -> User:
            return User(
                username=name,
                display_name=name,
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )

        boss = user("boss")  # ALL
        alice = user("alice")  # SELF
        bob = user("bob")  # SELF
        reader = user("requirement-reader")  # ALL, without feedback.view
        converter = user("converter")  # ALL, feedback.convert only
        session.add_all([boss, alice, bob, reader, converter])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=boss.id, role_id=role_all.id),
                UserRole(user_id=alice.id, role_id=role_self.id),
                UserRole(user_id=bob.id, role_id=role_self.id),
                UserRole(user_id=reader.id, role_id=requirement_reader_role.id),
                UserRole(user_id=converter.id, role_id=converter_role.id),
            ]
        )
        session.commit()

        ids = {
            "boss": boss.id,
            "alice": alice.id,
            "bob": bob.id,
            "reader": reader.id,
            "converter": converter.id,
        }
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


def _create_req(client, headers, **overrides) -> dict:
    body = {"title": "需求标题", "requirement_type": "FEATURE", "description": "需求描述内容"}
    import jwt

    uid = int(
        jwt.decode(headers["Authorization"].split()[1], options={"verify_signature": False})["sub"]
    )
    body["participants"] = [
        {"user_id": uid, "role": role} for role in ("CONFIRM", "DEVELOP", "ACCEPT")
    ]
    body.update(overrides)
    r = client.post("/api/v1/requirements", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _create_feedback(client, headers, **overrides) -> dict:
    body = {
        "title": "反馈标题",
        "feedback_type": "SYSTEM_ISSUE",
        "description": "反馈描述",
        "recipient_ids": [
            p["id"]
            for p in client.get(
                "/api/v1/collaboration/people?kind=feedback", headers=headers
            ).json()["items"]
        ],
    }
    body.update(overrides)
    r = client.post("/api/v1/feedbacks", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# CRUD + revision                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("conversion", [False, True])
def test_new_requirement_requires_an_eligible_confirmer(req_api, conversion):
    client, db, headers, ids = req_api
    actor = headers["alice"]
    payload = {"requirement_type": "FEATURE", "description": "合规描述"}
    if conversion:
        feedback = _create_feedback(client, actor)
        path = f"/api/v1/feedbacks/{feedback['id']}/convert"
        payload.update(
            type="CREATE_NEW",
            revision=feedback["revision"],
            requirement_title="反馈转新需求",
        )
    else:
        path = "/api/v1/requirements"
        payload["title"] = "直接新建需求"

    tracked = (
        Requirement,
        RequirementParticipant,
        RequirementFeedback,
        CollaborationEvent,
        OperationLog,
    )
    before = [db.scalar(select(func.count()).select_from(model)) for model in tracked]
    missing = [
        payload,
        {**payload, "participants": [{"role": "DEVELOP", "user_id": ids["alice"]}]},
    ]
    for body in missing:
        rejected = client.post(path, headers=actor, json=body)
        assert rejected.status_code == 422, rejected.text
        assert "请至少指定一名需求确认人" in rejected.text

    ineligible = client.post(
        path,
        headers=actor,
        json={**payload, "participants": [{"role": "CONFIRM", "user_id": ids["converter"]}]},
    )
    assert ineligible.status_code == 422 and ineligible.json()["code"] == 42260
    assert [db.scalar(select(func.count()).select_from(model)) for model in tracked] == before
    if conversion:
        current = db.get(Feedback, feedback["id"])
        assert current.status == "NEW"
        assert current.revision == feedback["revision"] and current.main_requirement_id is None


def test_requirement_crud_and_optimistic_lock(req_api):
    client, _session, headers, _ids = req_api
    created = _create_req(client, headers["alice"], title="A 需求")
    assert created["requirement_no"].startswith("REQ-")
    assert created["status"] == "DRAFT"
    assert created["source"] == "DIRECT"
    assert created["revision"] == 1

    page = client.get("/api/v1/requirements", headers=headers["alice"]).json()
    assert page["total"] == 1
    assert {"items", "page", "page_size", "total"} <= page.keys()

    assert (
        client.get(f"/api/v1/requirements/{created['id']}", headers=headers["alice"]).status_code
        == 200
    )

    updated = client.patch(
        f"/api/v1/requirements/{created['id']}",
        headers=headers["alice"],
        json={"title": "改后需求", "revision": 1},
    )
    assert updated.status_code == 200 and updated.json()["revision"] == 2

    stale = client.patch(
        f"/api/v1/requirements/{created['id']}",
        headers=headers["alice"],
        json={"title": "再改", "revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["data"]["current_revision"] == 2


def test_creator_without_edit_permission_can_only_edit_own_draft_requirement(req_api):
    client, session, headers, ids = req_api
    participants = [
        {"user_id": ids["boss"], "role": role} for role in ("CONFIRM", "DEVELOP", "ACCEPT")
    ]
    created = _create_req(client, headers["alice"], participants=participants)
    assert created["can_edit_as_creator"] is None
    path = f"/api/v1/requirements/{created['id']}"
    session.execute(
        delete(RolePermission).where(
            RolePermission.role_id
            == select(Role.id).where(Role.code == "SELFROLE").scalar_subquery(),
            RolePermission.permission_id.in_(
                select(Permission.id).where(
                    Permission.code.in_(("rd.requirement.edit", "rd.requirement.status"))
                )
            ),
        )
    )
    session.commit()

    body = {"description": "创建人补充需求说明", "revision": created["revision"]}
    hidden = client.patch(path, headers=headers["bob"], json=body)
    assert hidden.status_code == 404, hidden.text
    for actor, editable in (("alice", True), ("reader", False)):
        detail = client.get(path, headers=headers[actor])
        assert detail.status_code == 200, detail.text
        assert detail.json()["can_edit_as_creator"] is editable
    forbidden = client.patch(path, headers=headers["reader"], json=body)
    assert forbidden.status_code == 403, forbidden.text
    listed = client.get("/api/v1/requirements", headers=headers["alice"])
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["can_edit_as_creator"] is None

    for method, route, payload in (
        ("PATCH", f"{path}/status", {"status": "CONFIRMED"}),
        ("PUT", f"{path}/participants", {"participants": participants}),
        ("DELETE", path, {"reason": "申请删除"}),
    ):
        rejected = client.request(
            method,
            route,
            headers=headers["alice"],
            json={**payload, "revision": created["revision"]},
        )
        assert rejected.status_code == 403, rejected.text

    saved = client.patch(path, headers=headers["alice"], json=body)
    assert saved.status_code == 200, saved.text
    current = saved.json()
    assert current["can_edit_as_creator"] is None
    assert current["status"] == "DRAFT"
    assert current["description"] == body["description"]
    assert current["revision"] == created["revision"] + 1
    assert_revision_conflict(
        client.patch(path, headers=headers["alice"], json=body),
        revision=current["revision"],
        updated_by=ids["alice"],
    )
    log = session.scalars(
        select(OperationLog).where(
            OperationLog.entity_type == "REQUIREMENT",
            OperationLog.entity_id == created["id"],
            OperationLog.action == "UPDATE",
        )
    ).one()
    assert log.operator_id == ids["alice"]
    assert log.before_data["description"] == created["description"]
    assert log.after_data["description"] == body["description"]

    confirmed = client.patch(
        f"{path}/status",
        headers=headers["boss"],
        json={"status": "CONFIRMED", "revision": current["revision"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    latest_revision = confirmed.json()["revision"]
    detail = client.get(path, headers=headers["alice"])
    assert detail.status_code == 200, detail.text
    assert detail.json()["can_edit_as_creator"] is False
    assert_revision_conflict(
        client.patch(
            path, headers=headers["alice"], json={**body, "revision": current["revision"]}
        ),
        revision=latest_revision,
        updated_by=ids["boss"],
    )
    next_edit = {"title": "确认后更新需求", "revision": latest_revision}
    rejected = client.patch(path, headers=headers["alice"], json=next_edit)
    assert rejected.status_code == 403, rejected.text

    edited = client.patch(path, headers=headers["boss"], json=next_edit)
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == next_edit["title"]
    assert edited.json()["revision"] == latest_revision + 1


def test_two_users_requirement_update_and_status_revision_contract(req_api):
    client, _session, headers, ids = req_api
    created = _create_req(client, headers["alice"])
    path = f"/api/v1/requirements/{created['id']}"
    assert client.get(path, headers=headers["alice"]).json()["revision"] == 1
    assert client.get(path, headers=headers["boss"]).json()["revision"] == 1
    assert (
        client.patch(
            path, headers=headers["alice"], json={"title": "A 保存", "revision": 1}
        ).status_code
        == 200
    )
    assert_revision_conflict(
        client.patch(path, headers=headers["boss"], json={"title": "B 保存", "revision": 1}),
        revision=2,
        updated_by=ids["alice"],
    )
    assert_revision_conflict(
        client.patch(
            f"{path}/status",
            headers=headers["boss"],
            json={"status": "CONFIRMED", "revision": 1},
        ),
        revision=2,
        updated_by=ids["alice"],
    )
    illegal = client.patch(
        f"{path}/status", headers=headers["boss"], json={"status": "DONE", "revision": 2}
    )
    assert illegal.status_code == 409 and illegal.json()["code"] != 40910


def test_requirement_status_machine(req_api):
    client, _session, headers, _ids = req_api
    req = _create_req(client, headers["alice"])
    rid = req["id"]

    def status(target, revision, **extra):
        return client.patch(
            f"/api/v1/requirements/{rid}/status",
            headers=headers["alice"],
            json={"status": target, "revision": revision, **extra},
        )

    # Illegal jump DRAFT -> DONE
    assert status("DONE", 1).status_code == 409
    # Manual ONLINE is not a ManualRequirementStatus -> 422
    assert status("ONLINE", 1).status_code == 422

    r = status("CONFIRMED", 1)
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED"
    assert status("PLANNED", r.json()["revision"]).status_code == 422
    r = status("DEVELOPING", r.json()["revision"])
    r = status("TESTING", r.json()["revision"])
    r = status("DONE", r.json()["revision"])
    assert r.status_code == 200 and r.json()["status"] == "DONE"
    # DONE -> DEVELOPING requires a reason.
    assert status("DEVELOPING", r.json()["revision"]).status_code == 422
    reopened = status("DEVELOPING", r.json()["revision"], reason="重新开发")
    assert reopened.status_code == 200 and reopened.json()["status"] == "DEVELOPING"


# --------------------------------------------------------------------------- #
# data scope / IDOR                                                            #
# --------------------------------------------------------------------------- #
def test_self_scope_isolation(req_api):
    client, _session, headers, _ids = req_api
    alice_req = _create_req(client, headers["alice"], title="alice-req")

    assert (
        client.get(f"/api/v1/requirements/{alice_req['id']}", headers=headers["bob"]).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/requirements/{alice_req['id']}",
            headers=headers["bob"],
            json={"title": "越权改", "revision": 1},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/requirements/{alice_req['id']}/status",
            headers=headers["bob"],
            json={"status": "CONFIRMED", "revision": 1},
        ).status_code
        == 404
    )
    # ALL boss can access.
    assert (
        client.get(f"/api/v1/requirements/{alice_req['id']}", headers=headers["boss"]).status_code
        == 200
    )


# --------------------------------------------------------------------------- #
# Feedback -> Requirement convert                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("accept_on_convert", [False, True])
def test_convert_create_new(req_api, accept_on_convert):
    client, session, headers, ids = req_api
    fb = _create_feedback(client, headers["alice"], title="待转反馈")
    participants = [{"role": "CONFIRM", "user_id": ids["alice"]}]
    resp = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={
            "type": "CREATE_NEW",
            "revision": 1,
            "requirement_title": "由反馈转来的需求",
            "requirement_type": "FEATURE",
            "description": "整理后的研发需求",
            "participants": participants,
            **({"accept_on_convert": True} if accept_on_convert else {}),
        },
    )
    assert resp.status_code == 200, resp.text
    req = resp.json()
    assert req["source"] == "FEEDBACK"
    assert req["status"] == "DRAFT"
    assert req["system_id"] is None
    assigned = client.get(
        f"/api/v1/requirements/{req['id']}/participants", headers=headers["alice"]
    ).json()
    assert assigned["participants"] == [
        {**participants[0], "active": True, "display_name": "alice"}
    ]

    detail = client.get(f"/api/v1/feedbacks/{fb['id']}", headers=headers["alice"]).json()
    assert detail["status"] == "REQUIREMENT_LINKED"
    assert detail["main_requirement_id"] == req["id"]
    assert detail["revision"] == fb["revision"] + 1
    info = client.get(
        f"/api/v1/feedbacks/{fb['id']}/collaboration", headers=headers["alice"]
    ).json()
    assert (
        info["handler_id"] == info["accepted_by"] == (ids["alice"] if accept_on_convert else None)
    )
    assert bool(info["accepted_at"]) == accept_on_convert

    # Requirement -> source feedback traceability.
    linked = client.get(f"/api/v1/requirements/{req['id']}/feedbacks", headers=headers["alice"])
    assert linked.status_code == 200
    assert [f["feedback_id"] for f in linked.json()] == [fb["id"]]
    assert linked.json()[0]["is_primary"] is True

    # Duplicate convert -> 409.
    again = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={
            "type": "CREATE_NEW",
            "revision": detail["revision"],
            "requirement_title": "再转一次",
            "requirement_type": "FEATURE",
            "description": "描述",
            "participants": participants,
        },
    )
    assert again.status_code == 409
    assert again.json()["code"] != 40910
    assert_revision_conflict(
        client.post(
            f"/api/v1/feedbacks/{fb['id']}/convert",
            headers=headers["alice"],
            json={
                "type": "CREATE_NEW",
                "revision": 1,
                "requirement_title": "旧版本再次转换",
                "requirement_type": "FEATURE",
                "description": "描述",
                "participants": participants,
            },
        ),
        revision=detail["revision"],
        updated_by=ids["alice"],
    )

    # Audit chain.
    fb_actions = set(
        session.scalars(
            select(OperationLog.action).where(
                OperationLog.entity_type == "FEEDBACK", OperationLog.entity_id == fb["id"]
            )
        ).all()
    )
    assert "CONVERT_REQUIREMENT" in fb_actions
    req_actions = set(
        session.scalars(
            select(OperationLog.action).where(
                OperationLog.entity_type == "REQUIREMENT", OperationLog.entity_id == req["id"]
            )
        ).all()
    )
    assert "CREATE_FROM_FEEDBACK" in req_actions


def test_conversion_system_selection_is_scoped_to_new_requirement(req_api):
    client, session, headers, ids = req_api
    session.add_all(
        [
            BusinessSystem(id=31, code="TARGET", name="客户服务"),
            BusinessSystem(id=32, code="OTHER", name="其他系统"),
            BusinessSystem(id=33, code="DISABLED", name="已停用", enabled=False),
        ]
    )
    session.commit()
    converter = headers["converter"]
    options = client.get("/api/v1/systems/options", headers=converter)
    assert options.status_code == 200
    assert sorted(options.json(), key=lambda row: row["id"]) == [
        {"id": 31, "name": "客户服务"},
        {"id": 32, "name": "其他系统"},
    ]
    assert client.get("/api/v1/systems", headers=converter).status_code == 403
    feedback = _create_feedback(client, headers["alice"])
    path = f"/api/v1/feedbacks/{feedback['id']}/convert"
    payload = {
        "type": "CREATE_NEW",
        "revision": feedback["revision"],
        "requirement_title": "选择业务系统",
        "requirement_type": "FEATURE",
        "description": "从无系统的反馈转入需求",
        "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
    }
    for invalid in (33, 999, -1):
        rejected = client.post(path, headers=converter, json={**payload, "system_id": invalid})
        assert rejected.status_code == 422
    rejected = client.post(
        path,
        headers=headers["alice"],
        json={
            "type": "LINK_EXISTING",
            "revision": feedback["revision"],
            "requirement_id": 1,
            "system_id": 31,
        },
    )
    assert rejected.status_code == 422
    assert session.scalar(select(Requirement.id)) is None
    created = client.post(path, headers=converter, json={**payload, "system_id": 31})
    assert created.status_code == 200, created.text
    assert created.json()["system_id"] == 31
    detail = client.get(f"/api/v1/feedbacks/{feedback['id']}", headers=headers["alice"]).json()
    assert detail["system_id"] is None
    assert detail["main_requirement_id"] == created.json()["id"]

    bound = _create_feedback(client, headers["alice"], system_id=32)
    bound_path = f"/api/v1/feedbacks/{bound['id']}/convert"
    payload["revision"] = bound["revision"]
    assert (
        client.post(bound_path, headers=converter, json={**payload, "system_id": 31}).status_code
        == 422
    )
    inherited = client.post(bound_path, headers=converter, json=payload)
    assert inherited.status_code == 200, inherited.text
    assert inherited.json()["system_id"] == 32


def test_convert_link_existing(req_api):
    client, session, headers, ids = req_api
    existing = _create_req(
        client,
        headers["alice"],
        title="已有需求",
        participants=[{"role": "CONFIRM", "user_id": ids["alice"]}],
    )
    participants = select(RequirementParticipant).where(
        RequirementParticipant.requirement_id == existing["id"]
    )
    historical_confirmer = session.scalar(participants)
    assert historical_confirmer is not None
    historical_confirmer.active = False
    session.commit()
    fb = _create_feedback(client, headers["alice"], title="归并到已有")
    resp = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={"type": "LINK_EXISTING", "revision": 1, "requirement_id": existing["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == existing["id"]
    detail = client.get(f"/api/v1/feedbacks/{fb['id']}", headers=headers["alice"]).json()
    assert detail["status"] == "REQUIREMENT_LINKED"
    assert detail["main_requirement_id"] == existing["id"]
    people = list(session.scalars(participants))
    assert [(p.role, p.user_id, p.active) for p in people] == [("CONFIRM", ids["alice"], False)]


def test_convert_missing_fields_is_422(req_api):
    client, _session, headers, _ids = req_api
    fb = _create_feedback(client, headers["alice"])
    # CREATE_NEW without required fields.
    assert (
        client.post(
            f"/api/v1/feedbacks/{fb['id']}/convert",
            headers=headers["alice"],
            json={"type": "CREATE_NEW", "revision": 1},
        ).status_code
        == 422
    )
    # LINK_EXISTING without requirement_id.
    assert (
        client.post(
            f"/api/v1/feedbacks/{fb['id']}/convert",
            headers=headers["alice"],
            json={"type": "LINK_EXISTING", "revision": 1},
        ).status_code
        == 422
    )


def test_accept_and_convert_requires_explicit_acceptance(req_api):
    client, session, headers, ids = req_api
    feedback = _create_feedback(client, headers["alice"], recipient_ids=[ids["alice"]])
    path = f"/api/v1/feedbacks/{feedback['id']}/accept-and-convert"
    payload = {
        "type": "CREATE_NEW",
        "revision": feedback["revision"],
        "requirement_title": "从反馈新建",
        "requirement_type": "FEATURE",
        "description": "描述内容",
        "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
    }
    for invalid in ({}, {"accept_on_convert": False}):
        response = client.post(path, headers=headers["alice"], json={**payload, **invalid})
        assert response.status_code == 422, response.text
        assert response.json()["detail"][0]["loc"] == ["body", "accept_on_convert"]
    assert session.scalar(select(Requirement.id)) is None

    response = client.post(
        path, headers=headers["alice"], json={**payload, "accept_on_convert": True}
    )
    assert response.status_code == 200, response.text
    row = session.get(Feedback, feedback["id"])
    assert row.main_requirement_id == response.json()["id"]
    assert row.status == "REQUIREMENT_LINKED" and row.revision == feedback["revision"] + 1
    assert row.handler_id == row.accepted_by == ids["alice"] and row.accepted_at


def test_accept_and_link_rechecks_target_scope_after_lock(req_api, monkeypatch):
    client, session, headers, ids = req_api
    target = _create_req(
        client, headers["bob"], participants=[{"role": "CONFIRM", "user_id": ids["alice"]}]
    )
    assert (
        client.get(f"/api/v1/requirements/{target['id']}", headers=headers["alice"]).status_code
        == 200
    )
    feedback = _create_feedback(client, headers["alice"], recipient_ids=[ids["alice"]])
    refresh = session.refresh

    def refresh_after_participant_change(item, *args, **kwargs):
        if isinstance(item, Requirement) and kwargs.get("with_for_update"):
            session.execute(
                update(RequirementParticipant)
                .where(RequirementParticipant.requirement_id == target["id"])
                .values(active=False)
            )
        return refresh(item, *args, **kwargs)

    monkeypatch.setattr(session, "refresh", refresh_after_participant_change)
    response = client.post(
        f"/api/v1/feedbacks/{feedback['id']}/accept-and-convert",
        headers=headers["alice"],
        json={
            "type": "LINK_EXISTING",
            "revision": feedback["revision"],
            "requirement_id": target["id"],
            "accept_on_convert": True,
        },
    )
    assert response.status_code == 404, response.text
    assert session.scalar(select(RequirementFeedback.id)) is None
    row = session.get(Feedback, feedback["id"])
    assert row.revision == feedback["revision"] and row.accepted_at is None


@pytest.mark.parametrize("target_status", ["ONLINE", "CANCELED"])
def test_online_feedback_cannot_link_to_terminal_repair(req_api, target_status):
    client, session, headers, ids = req_api
    actor = headers["alice"]
    source = _create_req(client, actor)
    target = _create_req(client, actor)
    feedback = _create_feedback(client, actor, recipient_ids=[ids["alice"]])
    session.get(Requirement, source["id"]).status = "ONLINE"
    session.get(Requirement, target["id"]).status = target_status
    session.add(RequirementOnlineFeedback(requirement_id=source["id"], feedback_id=feedback["id"]))
    session.commit()
    fields = {
        "type": "LINK_EXISTING",
        "revision": feedback["revision"],
        "requirement_id": target["id"],
    }

    response = client.post(
        f"/api/v1/feedbacks/{feedback['id']}/accept-and-convert",
        headers=actor,
        json={**fields, "accept_on_convert": True},
    )
    assert response.status_code == 409 and response.json()["code"] == 40989, response.text
    assert session.scalar(select(RequirementFeedback.id)) is None
    row = session.get(Feedback, feedback["id"])
    assert row.status == "NEW" and row.accepted_at is None

    ordinary = _create_feedback(client, actor, recipient_ids=[ids["alice"]])
    allowed = client.post(f"/api/v1/feedbacks/{ordinary['id']}/convert", headers=actor, json=fields)
    assert allowed.status_code == 200, allowed.text


@pytest.mark.parametrize("accept_on_convert", [False, True])
def test_convert_link_existing_out_of_scope_is_404(req_api, accept_on_convert):
    client, session, headers, _ids = req_api
    alice_req = _create_req(client, headers["alice"], title="alice私有需求")
    bob_fb = _create_feedback(client, headers["bob"], title="bob反馈")
    # bob (SELF) cannot link to a requirement he cannot see.
    resp = client.post(
        f"/api/v1/feedbacks/{bob_fb['id']}/convert",
        headers=headers["bob"],
        json={
            "type": "LINK_EXISTING",
            "revision": 1,
            "requirement_id": alice_req["id"],
            "accept_on_convert": accept_on_convert,
        },
    )
    assert resp.status_code == 404
    # bob's feedback stays NEW (transaction did nothing).
    assert (
        client.get(f"/api/v1/feedbacks/{bob_fb['id']}", headers=headers["bob"]).json()["status"]
        == "NEW"
    )
    row = session.get(Feedback, bob_fb["id"])
    assert row.revision == bob_fb["revision"]
    assert row.handler_id is row.accepted_by is row.accepted_at is row.main_requirement_id is None
    assert session.scalar(select(RequirementFeedback.id)) is None


def test_linked_feedback_requires_both_permissions_and_filters_feedback_scope(req_api):
    client, session, headers, _ids = req_api
    requirement = _create_req(client, headers["alice"], title="可见需求")
    alice_feedback = _create_feedback(client, headers["alice"], title="本人反馈")
    bob_feedback = _create_feedback(client, headers["bob"], title="他人反馈")
    session.add_all(
        [
            RequirementFeedback(requirement_id=requirement["id"], feedback_id=alice_feedback["id"]),
            RequirementFeedback(requirement_id=requirement["id"], feedback_id=bob_feedback["id"]),
        ]
    )
    session.commit()

    forbidden = client.get(
        f"/api/v1/requirements/{requirement['id']}/feedbacks", headers=headers["reader"]
    )
    assert forbidden.status_code == 403

    visible = client.get(
        f"/api/v1/requirements/{requirement['id']}/feedbacks", headers=headers["alice"]
    )
    assert visible.status_code == 200
    assert [item["feedback_id"] for item in visible.json()] == [alice_feedback["id"]]


def test_converter_without_requirement_view_can_create_but_not_link(req_api):
    client, _session, headers, ids = req_api
    existing = _create_req(client, headers["alice"], title="已有需求")
    linked_feedback = _create_feedback(client, headers["alice"], title="不能关联")
    link = client.post(
        f"/api/v1/feedbacks/{linked_feedback['id']}/convert",
        headers=headers["converter"],
        json={"type": "LINK_EXISTING", "revision": 1, "requirement_id": existing["id"]},
    )
    assert link.status_code == 403

    new_feedback = _create_feedback(client, headers["alice"], title="可以新建")
    path = f"/api/v1/feedbacks/{new_feedback['id']}/convert"
    payload = {
        "type": "CREATE_NEW",
        "revision": 1,
        "requirement_title": "从反馈新建",
        "requirement_type": "FEATURE",
        "description": "描述内容",
        "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
    }
    for route in (path, path.replace("/convert", "/accept-and-convert")):
        combined = client.post(
            route, headers=headers["converter"], json={**payload, "accept_on_convert": True}
        )
        assert combined.status_code == 403, combined.text
    assert (
        client.get(path.removesuffix("/convert"), headers=headers["alice"]).json() == new_feedback
    )
    create = client.post(path, headers=headers["converter"], json=payload)
    assert create.status_code == 200, create.text


def test_converter_can_edit_their_draft_with_view_permission_until_frozen(req_api):
    client, session, headers, ids = req_api
    feedback = _create_feedback(client, headers["alice"])
    actor = headers["converter"]
    fields = {
        "requirement_type": "FEATURE",
        "description": "由反馈整理的内容",
        "participants": [{"role": "CONFIRM", "user_id": ids["boss"]}],
    }
    converted = client.post(
        f"/api/v1/feedbacks/{feedback['id']}/convert",
        headers=actor,
        json={
            **fields,
            "type": "CREATE_NEW",
            "revision": feedback["revision"],
            "requirement_title": "反馈转换生成的需求",
        },
    )
    assert converted.status_code == 200, converted.text
    created = converted.json()
    assert created["source"] == "FEEDBACK"
    assert created["status"] == "DRAFT"
    assert created["can_edit_as_creator"] is None
    item = session.get(Requirement, created["id"])
    assert item.created_by == ids["converter"]

    path = f"/api/v1/requirements/{created['id']}"
    body = {"title": "转换人补充需求标题", "revision": created["revision"]}
    forbidden = client.patch(path, headers=actor, json=body)
    assert forbidden.status_code == 403, forbidden.text

    reader_role_id = session.scalar(select(Role.id).where(Role.code == "REQUIREMENT_READER"))
    session.add(UserRole(user_id=ids["converter"], role_id=reader_role_id))
    session.commit()
    direct_create = client.post(
        "/api/v1/requirements", headers=actor, json={**fields, "title": "尝试直接创建"}
    )
    assert direct_create.status_code == 403, direct_create.text
    detail = client.get(path, headers=actor)
    assert detail.status_code == 200, detail.text
    assert detail.json()["can_edit_as_creator"] is True
    saved = client.patch(path, headers=actor, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["title"] == body["title"]
    assert saved.json()["revision"] == created["revision"] + 1

    version = Version(id=1, version_no="1.0.0", name="历史冻结版本", release_frozen=True)
    session.add(version)
    item.current_version_id = version.id
    session.commit()
    session.expire_all()
    detail = client.get(path, headers=actor)
    assert detail.status_code == 200, detail.text
    assert detail.json()["release_frozen"] is True
    assert detail.json()["can_edit_as_creator"] is False
    frozen = client.patch(
        path,
        headers=actor,
        json={"title": "尝试编辑冻结需求", "revision": saved.json()["revision"]},
    )
    assert frozen.status_code == 409, frozen.text
    assert frozen.json()["code"] == 40986


def test_accept_and_convert_requires_in_scope_current_new_feedback_and_eligible_actor(req_api):
    client, session, headers, ids = req_api
    feedback = _create_feedback(client, headers["alice"], recipient_ids=[ids["alice"]])
    path = f"/api/v1/feedbacks/{feedback['id']}"
    payload = {
        "type": "CREATE_NEW",
        "revision": feedback["revision"],
        "accept_on_convert": True,
        "requirement_title": "需要有效受理",
        "requirement_type": "FEATURE",
        "description": "描述内容",
        "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
    }
    initial_logs = session.scalar(select(func.count(OperationLog.id)))
    initial_events = session.scalar(select(func.count(CollaborationEvent.id)))
    assert client.post(f"{path}/convert", headers=headers["bob"], json=payload).status_code == 404
    stale = client.post(
        f"{path}/convert", headers=headers["boss"], json={**payload, "revision": 999}
    )
    assert_revision_conflict(stale, revision=feedback["revision"], updated_by=ids["alice"])
    unauthorized = client.post(
        f"{path}/convert",
        headers=headers["boss"],
        json={**payload, "accept_reason": "普通非接收人"},
    )
    assert unauthorized.status_code == 403, unauthorized.text
    assert client.get(path, headers=headers["alice"]).json() == feedback
    row = session.get(Feedback, feedback["id"])
    assert row.handler_id is row.accepted_by is row.accepted_at is None
    assert session.scalar(select(Requirement.id)) is None
    assert session.scalar(select(RequirementFeedback.id)) is None
    assert session.scalar(select(func.count(OperationLog.id))) == initial_logs
    assert session.scalar(select(func.count(CollaborationEvent.id))) == initial_events

    accepted = client.patch(
        f"{path}/status",
        headers=headers["alice"],
        json={"status": "ACCEPTED", "revision": feedback["revision"]},
    )
    assert accepted.status_code == 200, accepted.text
    # SQLite drops time zone info when materializing the row from the database.
    session.refresh(row)
    before_rejected_convert = client.get(path, headers=headers["alice"]).json()
    prior_collaboration = client.get(f"{path}/collaboration", headers=headers["alice"]).json()
    response = client.post(
        f"{path}/convert",
        headers=headers["alice"],
        json={**payload, "revision": accepted.json()["revision"]},
    )
    assert response.status_code == 409 and response.json()["code"] == 40911
    assert client.get(path, headers=headers["alice"]).json() == before_rejected_convert
    assert (
        client.get(f"{path}/collaboration", headers=headers["alice"]).json() == prior_collaboration
    )
    assert session.scalar(select(Requirement.id)) is None


def test_accept_and_link_existing_records_actual_delegated_operator(req_api):
    client, session, headers, ids = req_api
    role = session.scalar(select(Role).where(Role.code == "ALLROLE"))
    role.code = "DEVELOPMENT_LEAD"
    role.is_system = True
    session.commit()
    existing = _create_req(client, headers["alice"], title="已有需求")
    feedback = _create_feedback(client, headers["alice"], recipient_ids=[ids["alice"]])
    path = f"/api/v1/feedbacks/{feedback['id']}"
    payload = {
        "type": "LINK_EXISTING",
        "revision": feedback["revision"],
        "requirement_id": existing["id"],
        "accept_on_convert": True,
    }
    for reason, code in [(None, 403), ("   ", 403), ("短", 422), ("长" * 501, 422)]:
        rejected = client.post(
            f"{path}/convert", headers=headers["boss"], json={**payload, "accept_reason": reason}
        )
        assert rejected.status_code == code, rejected.text
    assert client.get(path, headers=headers["alice"]).json() == feedback

    reason = "接收人暂时无法处理, 由主管代受理"
    linked = client.post(
        f"{path}/convert", headers=headers["boss"], json={**payload, "accept_reason": reason}
    )
    assert linked.status_code == 200, linked.text
    assert linked.json() == existing
    row = session.get(Feedback, feedback["id"])
    assert row.status == "REQUIREMENT_LINKED" and row.revision == feedback["revision"] + 1
    assert row.handler_id == row.accepted_by == ids["boss"]
    assert row.accepted_at
    relation = session.scalars(select(RequirementFeedback)).one()
    assert relation.requirement_id == existing["id"] and relation.feedback_id == feedback["id"]
    assert relation.is_primary

    audit = session.scalars(
        select(OperationLog).where(OperationLog.action == "CONVERT_REQUIREMENT")
    ).one()
    assert audit.operator_id == ids["boss"] and audit.before_data == {"status": "NEW"}
    audit_data = dict(audit.after_data)
    accepted_at = datetime.fromisoformat(audit_data.pop("accepted_at"))
    assert accepted_at.replace(tzinfo=None) == row.accepted_at.replace(tzinfo=None)
    assert audit_data == {
        "status": "REQUIREMENT_LINKED",
        "requirement_id": existing["id"],
        "convert_type": "LINK_EXISTING",
        "accept_on_convert": True,
        "accept_reason": reason,
        "handler_id": ids["boss"],
        "accepted_by": ids["boss"],
    }
    events = session.scalars(
        select(CollaborationEvent).where(
            CollaborationEvent.entity_type == "FEEDBACK",
            CollaborationEvent.action.in_(("STATUS_ACCEPTED", "STATUS_REQUIREMENT_LINKED")),
        )
    ).all()
    assert [(item.action, item.actor_id, item.recipient_ids) for item in events] == [
        ("STATUS_REQUIREMENT_LINKED", ids["boss"], [ids["alice"]])
    ]


def test_accept_and_convert_rolls_back_when_image_binding_fails(req_api, monkeypatch):
    client, session, headers, ids = req_api
    feedback = _create_feedback(client, headers["alice"], recipient_ids=[ids["alice"]])
    path = f"/api/v1/feedbacks/{feedback['id']}"
    initial_logs = session.scalar(select(func.count(OperationLog.id)))
    initial_events = session.scalar(select(func.count(CollaborationEvent.id)))

    def request_db():
        # A distinct request session ensures teardown rolls back any uncommitted inserts.
        with Session(session.get_bind()) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, request_db)
    invalid = client.post(
        f"{path}/convert",
        headers=headers["alice"],
        json={
            "type": "CREATE_NEW",
            "revision": feedback["revision"],
            "accept_on_convert": True,
            "requirement_title": "不能提交的图文需求",
            "requirement_type": "FEATURE",
            "description": "描述未引用任何图片",
            "description_images": {"local-unused": "data:image/png;base64,iVBORw0KGgo="},
            "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
        },
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == 42265
    assert client.get(path, headers=headers["alice"]).json() == feedback
    row = session.get(Feedback, feedback["id"])
    assert row.handler_id is row.accepted_by is row.accepted_at is None
    assert session.scalar(select(Requirement.id)) is None
    assert session.scalar(select(RequirementFeedback.id)) is None
    assert session.scalar(select(func.count(OperationLog.id))) == initial_logs
    assert session.scalar(select(func.count(CollaborationEvent.id))) == initial_events


def test_convert_stale_revision_rolls_back(req_api):
    client, session, headers, ids = req_api
    fb = _create_feedback(client, headers["alice"], title="并发反馈")
    before = session.scalar(select(Requirement).where(Requirement.title == "并发反馈"))
    assert before is None
    req_count_before = len(session.scalars(select(Requirement.id)).all())

    resp = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={
            "type": "CREATE_NEW",
            "revision": 999,  # stale
            "requirement_title": "不该被创建",
            "requirement_type": "FEATURE",
            "description": "should roll back",
            "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
        },
    )
    assert resp.status_code == 409
    # No requirement was persisted; feedback unchanged.
    assert len(session.scalars(select(Requirement.id)).all()) == req_count_before
    assert (
        client.get(f"/api/v1/feedbacks/{fb['id']}", headers=headers["alice"]).json()["status"]
        == "NEW"
    )


# --------------------------------------------------------------------------- #
# DB-level uniqueness: one feedback -> at most one PRIMARY requirement          #
# --------------------------------------------------------------------------- #
def test_one_feedback_cannot_have_two_primary_requirements(req_api):
    client, session, headers, _ids = req_api
    fb = _create_feedback(client, headers["alice"])
    r1 = _create_req(client, headers["alice"], title="R1")
    r2 = _create_req(client, headers["alice"], title="R2")
    session.add(RequirementFeedback(requirement_id=r1["id"], feedback_id=fb["id"], is_primary=True))
    session.commit()
    session.add(RequirementFeedback(requirement_id=r2["id"], feedback_id=fb["id"], is_primary=True))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --------------------------------------------------------------------------- #
# audit before/after real fields                                              #
# --------------------------------------------------------------------------- #
def test_requirement_update_audit_before_after(req_api):
    client, session, headers, _ids = req_api
    req = _create_req(client, headers["alice"], title="原标题", priority="P2")
    client.patch(
        f"/api/v1/requirements/{req['id']}",
        headers=headers["alice"],
        json={"title": "新标题", "priority": "P0", "revision": 1},
    )
    log = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_type == "REQUIREMENT",
            OperationLog.entity_id == req["id"],
            OperationLog.action == "UPDATE",
        )
    )
    assert log is not None
    assert log.before_data == {"title": "原标题", "priority": "P2"}
    assert log.after_data == {"title": "新标题", "priority": "P0"}


# --------------------------------------------------------------------------- #
# OpenAPI contract sync                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("spec_name", ["openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"])
def test_openapi_declares_requirement_and_convert_contract(spec_name):
    spec = yaml.safe_load((SPEC_DIR / spec_name).read_text(encoding="utf-8"))
    paths = spec["paths"]
    assert "get" in paths["/requirements"] and "post" in paths["/requirements"]
    assert "get" in paths["/requirements/{requirement_id}"]
    assert "patch" in paths["/requirements/{requirement_id}"]
    assert "patch" in paths["/requirements/{requirement_id}/status"]
    assert "get" in paths["/requirements/{requirement_id}/feedbacks"]
    linked_feedbacks_description = paths["/requirements/{requirement_id}/feedbacks"]["get"][
        "description"
    ]
    assert "rd.requirement.view" in linked_feedbacks_description
    assert "rd.feedback.view" in linked_feedbacks_description
    assert "Feedback DataScope" in linked_feedbacks_description
    assert "rd.requirement.view" in paths["/feedbacks/{feedback_id}/convert"]["post"]["description"]

    schemas = spec["components"]["schemas"]
    assert "RequirementPage" in schemas
    assert "RequirementOut" in schemas
    convert = schemas["FeedbackConvertRequest"]["properties"]
    convert_type = resolve_openapi_ref(spec, convert["type"])
    assert set(convert_type["enum"]) == {"CREATE_NEW", "LINK_EXISTING"}
    assert "requirement_id" in convert
    assert "requirement_title" in convert


def test_description_image_access_and_history(req_api):
    client, _session, headers, _ids = req_api
    key = "local-787dbe55-0a0e-45a6-943a-9598ce8e6fda"
    data = {
        "description": f'<p>截图说明</p><img data-file-id="{key}">',
        "description_format": "HTML",
        "description_images": {key: "data:image/png;base64,iVBORw0KGgo="},
    }
    created = _create_req(client, headers["alice"], **data)
    assert created["description"] == '<p>截图说明</p><img data-file-id="1">'
    path = f"/api/v1/requirements/{created['id']}"
    image = path + "/images/1"
    assert client.get(image, headers=headers["alice"]).content == bytes.fromhex("89504e470d0a1a0a")
    assert client.get(image, headers=headers["boss"]).status_code == 200
    assert client.get(image, headers=headers["bob"]).status_code == 404
    assert client.get(image).status_code == 401
    other = _create_req(client, headers["alice"])
    assert (
        client.get(
            f"/api/v1/requirements/{other['id']}/images/1", headers=headers["alice"]
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/requirements/{other['id']}",
            headers=headers["alice"],
            json={
                "revision": 1,
                "description_format": "HTML",
                "description": created["description"],
            },
        ).status_code
        == 422
    )
    assert (
        client.patch(
            path, headers=headers["alice"], json={"revision": 1, "description": "新说明"}
        ).status_code
        == 200
    )
    # Confirmed snapshots may still contain the old file reference.
    assert client.get(image, headers=headers["alice"]).status_code == 200


def test_convert_and_edit_description_images(req_api):
    client, _session, headers, ids = req_api
    key = "local-12345678-1234-1234-1234-123456789abc"
    data = {
        "description": f'<p>反馈截图</p><img data-file-id="{key}">',
        "description_format": "HTML",
        "description_images": {key: "data:image/png;base64,iVBORw0KGgo="},
    }
    fb = _create_feedback(client, headers["alice"])
    response = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={
            **data,
            "type": "CREATE_NEW",
            "revision": fb["revision"],
            "requirement_title": "图文需求",
            "requirement_type": "FEATURE",
            "participants": [{"role": "CONFIRM", "user_id": ids["alice"]}],
        },
    )
    assert response.status_code == 200, response.text
    req = response.json()
    path = f"/api/v1/requirements/{req['id']}"
    response = client.patch(
        path,
        headers=headers["alice"],
        json={
            **data,
            "description": req["description"] + data["description"],
            "revision": req["revision"],
        },
    )
    assert response.status_code == 200
    assert response.json()["description"].endswith('<img data-file-id="2">')
    assert client.get(path + "/images/2", headers=headers["alice"]).status_code == 200

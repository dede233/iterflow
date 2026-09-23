from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from conftest import resolve_openapi_ref
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    BusinessModule,
    BusinessSystem,
    Feedback,
    OperationLog,
    Permission,
    Requirement,
    RequirementFeedback,
    Role,
    RolePermission,
    User,
    UserRole,
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
        Requirement.__table__,
        RequirementFeedback.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission, OperationLog, Feedback, Requirement, RequirementFeedback):
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
    body.update(overrides)
    r = client.post("/api/v1/requirements", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _create_feedback(client, headers, **overrides) -> dict:
    body = {"title": "反馈标题", "feedback_type": "SYSTEM_ISSUE", "description": "反馈描述"}
    body.update(overrides)
    r = client.post("/api/v1/feedbacks", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #
# CRUD + revision                                                             #
# --------------------------------------------------------------------------- #
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
    r = status("PLANNED", r.json()["revision"])
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
def test_convert_create_new(req_api):
    client, session, headers, _ids = req_api
    fb = _create_feedback(client, headers["alice"], title="待转反馈")
    resp = client.post(
        f"/api/v1/feedbacks/{fb['id']}/convert",
        headers=headers["alice"],
        json={
            "type": "CREATE_NEW",
            "revision": 1,
            "requirement_title": "由反馈转来的需求",
            "requirement_type": "FEATURE",
            "description": "整理后的研发需求",
        },
    )
    assert resp.status_code == 200, resp.text
    req = resp.json()
    assert req["source"] == "FEEDBACK"
    assert req["status"] == "CONFIRMED"

    detail = client.get(f"/api/v1/feedbacks/{fb['id']}", headers=headers["alice"]).json()
    assert detail["status"] == "REQUIREMENT_LINKED"
    assert detail["main_requirement_id"] == req["id"]

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
        },
    )
    assert again.status_code == 409

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


def test_convert_link_existing(req_api):
    client, _session, headers, _ids = req_api
    existing = _create_req(client, headers["alice"], title="已有需求")
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


def test_convert_link_existing_out_of_scope_is_404(req_api):
    client, _session, headers, _ids = req_api
    alice_req = _create_req(client, headers["alice"], title="alice私有需求")
    bob_fb = _create_feedback(client, headers["bob"], title="bob反馈")
    # bob (SELF) cannot link to a requirement he cannot see.
    resp = client.post(
        f"/api/v1/feedbacks/{bob_fb['id']}/convert",
        headers=headers["bob"],
        json={"type": "LINK_EXISTING", "revision": 1, "requirement_id": alice_req["id"]},
    )
    assert resp.status_code == 404
    # bob's feedback stays NEW (transaction did nothing).
    assert (
        client.get(f"/api/v1/feedbacks/{bob_fb['id']}", headers=headers["bob"]).json()["status"]
        == "NEW"
    )


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
    client, _session, headers, _ids = req_api
    existing = _create_req(client, headers["alice"], title="已有需求")
    linked_feedback = _create_feedback(client, headers["alice"], title="不能关联")
    link = client.post(
        f"/api/v1/feedbacks/{linked_feedback['id']}/convert",
        headers=headers["converter"],
        json={"type": "LINK_EXISTING", "revision": 1, "requirement_id": existing["id"]},
    )
    assert link.status_code == 403

    new_feedback = _create_feedback(client, headers["alice"], title="可以新建")
    create = client.post(
        f"/api/v1/feedbacks/{new_feedback['id']}/convert",
        headers=headers["converter"],
        json={
            "type": "CREATE_NEW",
            "revision": 1,
            "requirement_title": "从反馈新建",
            "requirement_type": "FEATURE",
            "description": "描述内容",
        },
    )
    assert create.status_code == 200, create.text


def test_convert_stale_revision_rolls_back(req_api):
    client, session, headers, _ids = req_api
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

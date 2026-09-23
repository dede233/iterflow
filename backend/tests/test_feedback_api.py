import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    AttachmentRelation,
    BusinessModule,
    BusinessSystem,
    Comment,
    Feedback,
    FileObject,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    ManualFeedbackStatus,
    StorageDriver,
    UserStatus,
)
from app.services.file_service import FileService

FEEDBACK_PERMISSIONS = {
    "rd.feedback.view",
    "rd.feedback.create",
    "rd.feedback.edit",
    "rd.feedback.convert",
    "sys.file.upload",
    "sys.file.download",
    "sys.file.delete",
}

SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"

FeedbackFixture = tuple[TestClient, Session, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def feedback_api(tmp_path: Path) -> Iterator[FeedbackFixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'feedback-api.db'}", connect_args={"check_same_thread": False}
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
        FileObject.__table__,
        AttachmentRelation.__table__,
        Comment.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (
        User,
        Role,
        Permission,
        OperationLog,
        BusinessSystem,
        BusinessModule,
        Feedback,
        FileObject,
        AttachmentRelation,
        Comment,
    ):
        counter = iter(range(1, 100000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        # Roles: MEMBER (SELF), CS/PM (ALL) — mirror the frozen scope matrix.
        member_role = Role(code="MEMBER", name="普通成员", data_scope=DataScope.SELF)
        cs_role = Role(
            code="CUSTOMER_SERVICE_OPERATIONS", name="客服/运营", data_scope=DataScope.ALL
        )
        pm_role = Role(code="PRODUCT_MANAGER", name="产品负责人", data_scope=DataScope.ALL)
        permissions = {
            code: Permission(code=code, name=code) for code in sorted(FEEDBACK_PERMISSIONS)
        }
        session.add_all([member_role, cs_role, pm_role, *permissions.values()])
        session.flush()

        def grant(role: Role, codes: set[str]) -> None:
            for code in codes:
                session.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))

        grant(member_role, {"rd.feedback.view", "rd.feedback.create", "rd.feedback.edit"})
        grant(cs_role, {"rd.feedback.view", "rd.feedback.create", "rd.feedback.edit"})
        grant(
            pm_role,
            {
                "rd.feedback.view",
                "rd.feedback.create",
                "rd.feedback.edit",
                "rd.feedback.convert",
                "sys.file.upload",
                "sys.file.download",
                "sys.file.delete",
            },
        )

        def make_user(username: str) -> User:
            user = User(
                username=username,
                display_name=username,
                password_hash="unused",
                status=UserStatus.ACTIVE,
                must_change_password=False,
            )
            return user

        alice = make_user("alice")  # MEMBER (SELF)
        bob = make_user("bob")  # MEMBER (SELF)
        cs = make_user("cs")  # CUSTOMER_SERVICE_OPERATIONS (ALL)
        pm = make_user("pm")  # PRODUCT_MANAGER (ALL)
        session.add_all([alice, bob, cs, pm])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=alice.id, role_id=member_role.id),
                UserRole(user_id=bob.id, role_id=member_role.id),
                UserRole(user_id=cs.id, role_id=cs_role.id),
                UserRole(user_id=pm.id, role_id=pm_role.id),
            ]
        )

        # Business systems / modules for relation validation + filtering.
        sys_a = BusinessSystem(code="SYS_A", name="系统A", enabled=True, sort_order=1)
        sys_b = BusinessSystem(code="SYS_B", name="系统B", enabled=True, sort_order=2)
        sys_off = BusinessSystem(code="SYS_OFF", name="停用系统", enabled=False, sort_order=3)
        session.add_all([sys_a, sys_b, sys_off])
        session.flush()
        mod_a1 = BusinessModule(system_id=sys_a.id, code="A1", name="模块A1", enabled=True)
        mod_b1 = BusinessModule(system_id=sys_b.id, code="B1", name="模块B1", enabled=True)
        mod_a_off = BusinessModule(system_id=sys_a.id, code="A_OFF", name="停用模块", enabled=False)
        session.add_all([mod_a1, mod_b1, mod_a_off])
        session.commit()

        ids = {
            "alice": alice.id,
            "bob": bob.id,
            "cs": cs.id,
            "pm": pm.id,
            "sys_a": sys_a.id,
            "sys_b": sys_b.id,
            "sys_off": sys_off.id,
            "mod_a1": mod_a1.id,
            "mod_b1": mod_b1.id,
            "mod_a_off": mod_a_off.id,
        }
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(ids[name])}"}
            for name in ("alice", "bob", "cs", "pm")
        }

        app.dependency_overrides[get_db] = lambda: session
        with TestClient(app) as client:
            yield client, session, headers, ids
        app.dependency_overrides.clear()

    for model, listener in listeners:
        event.remove(model, "before_insert", listener)
    engine.dispose()


def _create(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    body = {
        "title": "初始反馈标题",
        "feedback_type": "SYSTEM_ISSUE",
        "urgency": "NORMAL",
        "description": "详细描述内容",
    }
    body.update(overrides)
    response = client.post("/api/v1/feedbacks", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# CRUD + revision                                                             #
# --------------------------------------------------------------------------- #
def test_create_list_detail_and_optimistic_update(feedback_api):
    client, session, headers, _ids = feedback_api

    created = _create(client, headers["alice"], title="A 的反馈")
    assert created["feedback_no"].startswith("FB-")
    assert created["status"] == "NEW"
    assert created["revision"] == 1
    assert created["submitter_id"] == _ids_of(session, "alice")

    listed = client.get("/api/v1/feedbacks", headers=headers["alice"])
    assert listed.status_code == 200
    page = listed.json()
    assert page["total"] == 1
    assert {"items", "page", "page_size", "total"} <= page.keys()

    detail = client.get(f"/api/v1/feedbacks/{created['id']}", headers=headers["alice"])
    assert detail.status_code == 200

    updated = client.patch(
        f"/api/v1/feedbacks/{created['id']}",
        headers=headers["alice"],
        json={"title": "改后的标题", "revision": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["title"] == "改后的标题"

    # Stale revision must not silently overwrite.
    stale = client.patch(
        f"/api/v1/feedbacks/{created['id']}",
        headers=headers["alice"],
        json={"title": "再改", "revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["data"]["current_revision"] == 2


def test_invalid_feedback_type_is_rejected(feedback_api):
    client, _session, headers, _ids = feedback_api
    response = client.post(
        "/api/v1/feedbacks",
        headers=headers["alice"],
        json={
            "title": "标题",
            "feedback_type": "NOT_A_TYPE",
            "description": "描述内容",
        },
    )
    assert response.status_code == 422


def test_missing_feedback_returns_404(feedback_api):
    client, _session, headers, _ids = feedback_api
    assert client.get("/api/v1/feedbacks/999999", headers=headers["cs"]).status_code == 404


# --------------------------------------------------------------------------- #
# Data scope / IDOR                                                            #
# --------------------------------------------------------------------------- #
def test_self_scope_isolates_list_detail_and_update(feedback_api):
    client, _session, headers, _ids = feedback_api

    alice_fb = _create(client, headers["alice"], title="alice-owned")
    _create(client, headers["bob"], title="bob-owned")

    # Alice (SELF) only sees her own feedback in the list.
    alice_list = client.get("/api/v1/feedbacks", headers=headers["alice"]).json()
    assert alice_list["total"] == 1
    assert alice_list["items"][0]["title"] == "alice-owned"

    # Bob (SELF) cannot GET / PATCH / status-change Alice's feedback -> 404.
    assert (
        client.get(f"/api/v1/feedbacks/{alice_fb['id']}", headers=headers["bob"]).status_code == 404
    )
    assert (
        client.patch(
            f"/api/v1/feedbacks/{alice_fb['id']}",
            headers=headers["bob"],
            json={"title": "越权修改", "revision": 1},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/feedbacks/{alice_fb['id']}/status",
            headers=headers["bob"],
            json={"status": "ACCEPTED", "revision": 1},
        ).status_code
        == 404
    )


def test_all_scope_can_see_and_accept_others_feedback(feedback_api):
    client, _session, headers, _ids = feedback_api
    alice_fb = _create(client, headers["alice"], title="alice-owned")

    # CUSTOMER_SERVICE_OPERATIONS (ALL) sees and accepts another user's feedback.
    cs_list = client.get("/api/v1/feedbacks", headers=headers["cs"]).json()
    assert cs_list["total"] == 1
    accepted = client.patch(
        f"/api/v1/feedbacks/{alice_fb['id']}/status",
        headers=headers["cs"],
        json={"status": "ACCEPTED", "revision": 1},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"

    # PRODUCT_MANAGER (ALL) can also act on it (close, with reason).
    closed = client.patch(
        f"/api/v1/feedbacks/{alice_fb['id']}/status",
        headers=headers["pm"],
        json={"status": "CLOSED", "revision": accepted.json()["revision"], "reason": "无需处理"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"


def test_business_attachment_bypasses_generic_file_scope_only_after_feedback_auth(
    feedback_api, monkeypatch
):
    client, session, headers, _ids = feedback_api
    feedback = _create(client, headers["alice"], title="含附件反馈")
    item = FileObject(
        id=500,
        storage_key="uploads/opaque-key",
        original_name="evidence.txt",
        mime_type="text/plain",
        size=8,
        sha256=hashlib.sha256(b"evidence").hexdigest(),
        storage_driver=StorageDriver.LOCAL,
        created_by=1,
        updated_by=1,
    )
    session.add(item)
    session.flush()
    session.add(
        AttachmentRelation(file_id=item.id, entity_type="FEEDBACK", entity_id=feedback["id"])
    )
    session.commit()

    class MemoryStorage:
        def exists(self, _key: str) -> bool:
            return True

        def open(self, _key: str):
            return io.BytesIO(b"evidence")

    monkeypatch.setattr(FileService, "_storage", lambda self, _driver: MemoryStorage())

    assert client.get(f"/api/v1/files/{item.id}/download", headers=headers["pm"]).status_code == 404
    assert client.get(f"/api/v1/files/{item.id}/exists", headers=headers["pm"]).status_code == 404
    assert client.delete(f"/api/v1/files/{item.id}", headers=headers["pm"]).status_code == 409

    business = client.get(
        f"/api/v1/feedbacks/{feedback['id']}/attachments/{item.id}/download",
        headers=headers["alice"],
    )
    assert business.status_code == 200
    assert business.content == b"evidence"
    assert "\r" not in business.headers["content-disposition"]
    assert "\n" not in business.headers["content-disposition"]
    hidden_feedback = client.get(
        f"/api/v1/feedbacks/{feedback['id']}/attachments/{item.id}/download",
        headers=headers["bob"],
    )
    assert hidden_feedback.status_code == 404
    assert (
        "storage_key"
        not in client.get(f"/api/v1/feedbacks/{feedback['id']}", headers=headers["alice"]).json()
    )


def test_http_upload_rejects_spoofed_mime_before_storage(feedback_api, monkeypatch):
    client, _session, headers, _ids = feedback_api
    storage = Mock()
    monkeypatch.setattr(FileService, "_storage", lambda self, _driver: storage)

    response = client.post(
        "/api/v1/files",
        headers=headers["pm"],
        files={"file": ("spoof.png", b"not a png", "image/png")},
    )
    assert response.status_code == 422
    storage.upload.assert_not_called()


# --------------------------------------------------------------------------- #
# Status machine                                                              #
# --------------------------------------------------------------------------- #
def _status(client, headers, feedback_id, revision, status, **extra):
    return client.patch(
        f"/api/v1/feedbacks/{feedback_id}/status",
        headers=headers,
        json={"status": status, "revision": revision, **extra},
    )


def test_legal_status_transitions(feedback_api):
    client, _session, headers, _ids = feedback_api
    other = _create(client, headers["cs"], title="target-for-duplicate")

    # NEW -> ACCEPTED
    fb = _create(client, headers["cs"], title="lifecycle")
    r = _status(client, headers["cs"], fb["id"], 1, "ACCEPTED")
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED"

    # ACCEPTED -> DUPLICATE (needs duplicate_of_id)
    r = _status(
        client,
        headers["cs"],
        fb["id"],
        r.json()["revision"],
        "DUPLICATE",
        duplicate_of_id=other["id"],
    )
    assert r.status_code == 200 and r.json()["status"] == "DUPLICATE"
    assert r.json()["duplicate_of_id"] == other["id"]

    # DUPLICATE -> NEW (reopen clears duplicate_of_id, reason required)
    r = _status(client, headers["cs"], fb["id"], r.json()["revision"], "NEW", reason="重新打开")
    assert r.status_code == 200 and r.json()["status"] == "NEW"
    assert r.json()["duplicate_of_id"] is None

    # NEW -> CANNOT_REPRODUCE (reason required) -> NEW
    r = _status(
        client, headers["cs"], fb["id"], r.json()["revision"], "CANNOT_REPRODUCE", reason="无法复现"
    )
    assert r.status_code == 200 and r.json()["status"] == "CANNOT_REPRODUCE"
    r = _status(client, headers["cs"], fb["id"], r.json()["revision"], "NEW", reason="再看看")
    assert r.status_code == 200 and r.json()["status"] == "NEW"

    # NEW -> DUPLICATE directly
    r = _status(
        client,
        headers["cs"],
        fb["id"],
        r.json()["revision"],
        "DUPLICATE",
        duplicate_of_id=other["id"],
    )
    assert r.status_code == 200 and r.json()["status"] == "DUPLICATE"

    # NEW -> CLOSED (reason required), then CLOSED -> NEW
    fb2 = _create(client, headers["cs"], title="close-me")
    r = _status(client, headers["cs"], fb2["id"], 1, "CLOSED", reason="关闭原因")
    assert r.status_code == 200 and r.json()["status"] == "CLOSED"
    r = _status(client, headers["cs"], fb2["id"], r.json()["revision"], "NEW", reason="重开")
    assert r.status_code == 200 and r.json()["status"] == "NEW"


def test_reason_and_duplicate_validation(feedback_api):
    client, _session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="validate")

    # CANNOT_REPRODUCE without reason -> 422
    assert _status(client, headers["cs"], fb["id"], 1, "CANNOT_REPRODUCE").status_code == 422
    # CLOSED without reason -> 422
    assert _status(client, headers["cs"], fb["id"], 1, "CLOSED").status_code == 422
    # CLOSED with blank reason -> 422
    assert _status(client, headers["cs"], fb["id"], 1, "CLOSED", reason="   ").status_code == 422
    # DUPLICATE without duplicate_of_id -> 422
    assert _status(client, headers["cs"], fb["id"], 1, "DUPLICATE").status_code == 422
    # DUPLICATE of self -> 422
    assert (
        _status(
            client, headers["cs"], fb["id"], 1, "DUPLICATE", duplicate_of_id=fb["id"]
        ).status_code
        == 422
    )
    # DUPLICATE of a non-existent / invisible feedback -> 422
    assert (
        _status(client, headers["cs"], fb["id"], 1, "DUPLICATE", duplicate_of_id=987654).status_code
        == 422
    )

    # Reopen without reason -> 422 (first move to CLOSED with a reason)
    closed = _status(client, headers["cs"], fb["id"], 1, "CLOSED", reason="关闭")
    assert closed.status_code == 200
    assert (
        _status(client, headers["cs"], fb["id"], closed.json()["revision"], "NEW").status_code
        == 422
    )


def test_illegal_transitions_return_409(feedback_api):
    client, _session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="illegal")

    accepted = _status(client, headers["cs"], fb["id"], 1, "ACCEPTED")
    assert accepted.status_code == 200
    # ACCEPTED -> NEW is explicitly forbidden.
    assert (
        _status(
            client, headers["cs"], fb["id"], accepted.json()["revision"], "NEW", reason="x"
        ).status_code
        == 409
    )


@pytest.mark.parametrize("downstream", ["REQUIREMENT_LINKED", "ONLINE"])
def test_manual_downstream_statuses_are_rejected(feedback_api, downstream):
    client, _session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="no-manual-downstream")
    # Downstream statuses are not part of ManualFeedbackStatus -> request validation 422.
    resp = _status(client, headers["cs"], fb["id"], 1, downstream)
    assert resp.status_code == 422
    reread = client.get(f"/api/v1/feedbacks/{fb['id']}", headers=headers["cs"])
    assert reread.json()["status"] == "NEW"


@pytest.mark.parametrize("removed_status", ["PLANNED", "DEVELOPING", "TESTING"])
def test_feedback_does_not_define_rnd_lifecycle_statuses(feedback_api, removed_status):
    client, _session, headers, _ids = feedback_api
    assert removed_status not in FeedbackStatus._value2member_map_
    fb = _create(client, headers["cs"], title=f"no-{removed_status.lower()}")
    # The lifecycle states are neither valid FeedbackStatus values nor manually
    # assignable transition targets.
    assert _status(client, headers["cs"], fb["id"], 1, removed_status).status_code == 422


def test_status_change_uses_optimistic_lock(feedback_api):
    client, _session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="lock")
    first = _status(client, headers["cs"], fb["id"], 1, "ACCEPTED")
    assert first.status_code == 200
    # Reusing the stale revision must be rejected.
    assert _status(client, headers["cs"], fb["id"], 1, "CLOSED", reason="x").status_code == 409


# --------------------------------------------------------------------------- #
# system / module relation validation                                         #
# --------------------------------------------------------------------------- #
def test_system_module_relation_validation(feedback_api):
    client, _session, headers, ids = feedback_api

    # module without system -> 422
    assert (
        client.post(
            "/api/v1/feedbacks",
            headers=headers["alice"],
            json={
                "title": "标题",
                "feedback_type": "OTHER",
                "description": "描述",
                "module_id": ids["mod_a1"],
            },
        ).status_code
        == 422
    )
    # module not belonging to the given system -> 422
    assert (
        client.post(
            "/api/v1/feedbacks",
            headers=headers["alice"],
            json={
                "title": "标题",
                "feedback_type": "OTHER",
                "description": "描述",
                "system_id": ids["sys_a"],
                "module_id": ids["mod_b1"],
            },
        ).status_code
        == 422
    )
    # disabled system -> 422
    assert (
        client.post(
            "/api/v1/feedbacks",
            headers=headers["alice"],
            json={
                "title": "标题",
                "feedback_type": "OTHER",
                "description": "描述",
                "system_id": ids["sys_off"],
            },
        ).status_code
        == 422
    )
    # disabled module -> 422
    assert (
        client.post(
            "/api/v1/feedbacks",
            headers=headers["alice"],
            json={
                "title": "标题",
                "feedback_type": "OTHER",
                "description": "描述",
                "system_id": ids["sys_a"],
                "module_id": ids["mod_a_off"],
            },
        ).status_code
        == 422
    )
    # valid pair -> 200
    ok = client.post(
        "/api/v1/feedbacks",
        headers=headers["alice"],
        json={
            "title": "标题",
            "feedback_type": "OTHER",
            "description": "描述",
            "system_id": ids["sys_a"],
            "module_id": ids["mod_a1"],
        },
    )
    assert ok.status_code == 200


# --------------------------------------------------------------------------- #
# filters                                                                      #
# --------------------------------------------------------------------------- #
def test_list_filters_are_anded_with_scope(feedback_api):
    client, _session, headers, ids = feedback_api

    _create(
        client,
        headers["cs"],
        title="关键词命中",
        feedback_type="SYSTEM_ISSUE",
        urgency="URGENT",
        system_id=ids["sys_a"],
    )
    _create(
        client,
        headers["cs"],
        title="普通问题",
        feedback_type="DATA_ISSUE",
        urgency="NORMAL",
        system_id=ids["sys_b"],
    )
    _create(
        client,
        headers["alice"],
        title="alice的紧急",
        feedback_type="SYSTEM_ISSUE",
        urgency="URGENT",
    )

    # type filter
    r = client.get("/api/v1/feedbacks?feedback_type=SYSTEM_ISSUE", headers=headers["cs"]).json()
    assert r["total"] == 2
    # urgency filter
    r = client.get("/api/v1/feedbacks?urgency=NORMAL", headers=headers["cs"]).json()
    assert r["total"] == 1
    # system filter
    r = client.get(f"/api/v1/feedbacks?system_id={ids['sys_a']}", headers=headers["cs"]).json()
    assert r["total"] == 1
    # keyword filter
    r = client.get("/api/v1/feedbacks?keyword=关键词", headers=headers["cs"]).json()
    assert r["total"] == 1
    # blank keyword behaves as no filter
    r = client.get("/api/v1/feedbacks?keyword=%20%20", headers=headers["cs"]).json()
    assert r["total"] == 3

    # SELF scope + filter: alice only sees her own even with a matching type filter.
    r = client.get("/api/v1/feedbacks?feedback_type=SYSTEM_ISSUE", headers=headers["alice"]).json()
    assert r["total"] == 1
    assert r["items"][0]["title"] == "alice的紧急"


# --------------------------------------------------------------------------- #
# audit                                                                        #
# --------------------------------------------------------------------------- #
def test_audit_records_create_update_and_status_change(feedback_api):
    client, session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="审计")
    client.patch(
        f"/api/v1/feedbacks/{fb['id']}",
        headers=headers["cs"],
        json={"title": "审计改", "revision": 1},
    )
    client.patch(
        f"/api/v1/feedbacks/{fb['id']}/status",
        headers=headers["cs"],
        json={"status": "CLOSED", "revision": 2, "reason": "关闭理由"},
    )

    logs = session.scalars(
        select(OperationLog)
        .where(OperationLog.entity_type == "FEEDBACK", OperationLog.entity_id == fb["id"])
        .order_by(OperationLog.id)
    ).all()
    actions = [log.action for log in logs]
    assert actions == ["CREATE", "UPDATE", "STATUS_CHANGE"]

    status_log = logs[-1]
    # NEW -> CLOSED direct: the audit before-value must be the pre-update status.
    assert status_log.before_data["status"] == "NEW"
    assert status_log.after_data["status"] == "CLOSED"
    assert status_log.after_data["reason"] == "关闭理由"
    # No secrets ever leak into audit payloads.
    blob = str([(log.before_data, log.after_data) for log in logs])
    for secret in ("password", "token", "Bearer"):
        assert secret not in blob


# --------------------------------------------------------------------------- #
# UPDATE audit before/after real fields                                        #
# --------------------------------------------------------------------------- #
def test_update_audit_captures_real_before_and_after(feedback_api):
    client, session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="原标题", urgency="NORMAL")
    client.patch(
        f"/api/v1/feedbacks/{fb['id']}",
        headers=headers["cs"],
        json={"title": "新标题", "urgency": "URGENT", "revision": 1},
    )
    log = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_type == "FEEDBACK",
            OperationLog.entity_id == fb["id"],
            OperationLog.action == "UPDATE",
        )
    )
    assert log is not None
    assert log.before_data == {"title": "原标题", "urgency": "NORMAL"}
    assert log.after_data == {"title": "新标题", "urgency": "URGENT"}
    assert "revision" not in log.before_data


# --------------------------------------------------------------------------- #
# list system/module filter validation                                        #
# --------------------------------------------------------------------------- #
def test_list_filter_system_module_validation(feedback_api):
    client, session, headers, ids = feedback_api

    # unknown system -> 422
    assert (
        client.get("/api/v1/feedbacks?system_id=999999", headers=headers["cs"]).status_code == 422
    )
    # unknown module -> 422
    assert (
        client.get("/api/v1/feedbacks?module_id=999999", headers=headers["cs"]).status_code == 422
    )
    # mismatch (module belongs to a different system) -> 422
    assert (
        client.get(
            f"/api/v1/feedbacks?system_id={ids['sys_a']}&module_id={ids['mod_b1']}",
            headers=headers["cs"],
        ).status_code
        == 422
    )
    # disabled system is still allowed for historical filtering (not 422).
    # Seed one historical feedback directly under the disabled system.
    session.add(
        Feedback(
            feedback_no="FB-HIST-0001",
            title="历史反馈",
            feedback_type="OTHER",
            urgency="NORMAL",
            status="NEW",
            submitter_id=ids["cs"],
            description="历史",
            system_id=ids["sys_off"],
            created_by=ids["cs"],
            updated_by=ids["cs"],
        )
    )
    session.commit()
    hist = client.get(f"/api/v1/feedbacks?system_id={ids['sys_off']}", headers=headers["cs"])
    assert hist.status_code == 200
    assert hist.json()["total"] == 1


# --------------------------------------------------------------------------- #
# attachments                                                                  #
# --------------------------------------------------------------------------- #
def _upload(client, headers, feedback_id, name="a.txt", content=b"hello", mime="text/plain"):
    return client.post(
        f"/api/v1/feedbacks/{feedback_id}/attachments",
        headers=headers,
        files={"file": (name, content, mime)},
    )


def test_attachment_upload_list_download(feedback_api):
    client, _session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="附件反馈")

    up = _upload(client, headers["cs"], fb["id"], content=b"attachment-body")
    assert up.status_code == 200, up.text
    body = up.json()
    file_id = body["file_id"]
    # Business response must never leak storage_key / physical path.
    assert "storage_key" not in up.text and "path" not in body

    listed = client.get(f"/api/v1/feedbacks/{fb['id']}/attachments", headers=headers["cs"])
    assert listed.status_code == 200
    assert [a["file_id"] for a in listed.json()] == [file_id]

    dl = client.get(
        f"/api/v1/feedbacks/{fb['id']}/attachments/{file_id}/download", headers=headers["cs"]
    )
    assert dl.status_code == 200
    assert dl.content == b"attachment-body"


def test_self_cannot_access_others_attachment(feedback_api):
    client, _session, headers, _ids = feedback_api
    alice_fb = _create(client, headers["alice"], title="alice附件")
    up = _upload(client, headers["alice"], alice_fb["id"])
    assert up.status_code == 200
    file_id = up.json()["file_id"]

    # bob (SELF) cannot list or download attachments of alice's feedback.
    assert (
        client.get(
            f"/api/v1/feedbacks/{alice_fb['id']}/attachments", headers=headers["bob"]
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/feedbacks/{alice_fb['id']}/attachments/{file_id}/download",
            headers=headers["bob"],
        ).status_code
        == 404
    )


def test_all_scope_can_access_others_attachment(feedback_api):
    client, _session, headers, _ids = feedback_api
    alice_fb = _create(client, headers["alice"], title="alice附件2")
    file_id = _upload(client, headers["alice"], alice_fb["id"], content=b"body2").json()["file_id"]

    # CS (ALL) can list and download.
    assert (
        client.get(
            f"/api/v1/feedbacks/{alice_fb['id']}/attachments", headers=headers["cs"]
        ).status_code
        == 200
    )
    dl = client.get(
        f"/api/v1/feedbacks/{alice_fb['id']}/attachments/{file_id}/download", headers=headers["cs"]
    )
    assert dl.status_code == 200 and dl.content == b"body2"


def test_attachment_download_requires_matching_feedback(feedback_api):
    client, _session, headers, _ids = feedback_api
    fb1 = _create(client, headers["cs"], title="fb1")
    fb2 = _create(client, headers["cs"], title="fb2")
    file_id = _upload(client, headers["cs"], fb1["id"]).json()["file_id"]
    # A file attached to fb1 cannot be downloaded via fb2's path.
    assert (
        client.get(
            f"/api/v1/feedbacks/{fb2['id']}/attachments/{file_id}/download", headers=headers["cs"]
        ).status_code
        == 404
    )


# --------------------------------------------------------------------------- #
# comments                                                                     #
# --------------------------------------------------------------------------- #
def test_comment_list_and_create(feedback_api):
    client, session, headers, _ids = feedback_api
    fb = _create(client, headers["cs"], title="评论反馈")

    created = client.post(
        f"/api/v1/feedbacks/{fb['id']}/comments",
        headers=headers["cs"],
        json={"content": "第一条评论"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["content"] == "第一条评论"
    assert created.json()["entity_type"] == "FEEDBACK"

    listed = client.get(f"/api/v1/feedbacks/{fb['id']}/comments", headers=headers["cs"])
    assert listed.status_code == 200
    assert [c["content"] for c in listed.json()] == ["第一条评论"]

    # COMMENT_CREATE is audited.
    assert (
        session.scalar(
            select(OperationLog).where(
                OperationLog.entity_type == "FEEDBACK",
                OperationLog.entity_id == fb["id"],
                OperationLog.action == "COMMENT_CREATE",
            )
        )
        is not None
    )


def test_self_cannot_comment_on_others_feedback(feedback_api):
    client, _session, headers, _ids = feedback_api
    alice_fb = _create(client, headers["alice"], title="alice评论")
    # bob (SELF) can neither read nor post comments on alice's feedback.
    assert (
        client.get(
            f"/api/v1/feedbacks/{alice_fb['id']}/comments", headers=headers["bob"]
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/feedbacks/{alice_fb['id']}/comments",
            headers=headers["bob"],
            json={"content": "越权评论"},
        ).status_code
        == 404
    )
    # alice can comment on her own.
    assert (
        client.post(
            f"/api/v1/feedbacks/{alice_fb['id']}/comments",
            headers=headers["alice"],
            json={"content": "我的评论"},
        ).status_code
        == 200
    )


# --------------------------------------------------------------------------- #
# OpenAPI contract sync                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("spec_name", ["openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"])
def test_openapi_specs_declare_feedback_status_contract(spec_name):
    spec = yaml.safe_load((SPEC_DIR / spec_name).read_text(encoding="utf-8"))

    status_path = spec["paths"]["/feedbacks/{feedback_id}/status"]
    assert "patch" in status_path

    schemas = spec["components"]["schemas"]
    assert set(schemas["FeedbackStatusChange"]["properties"]["status"]["enum"]) == {
        s.value for s in ManualFeedbackStatus
    }
    assert set(schemas["Feedback"]["properties"]["status"]["enum"]) == {
        s.value for s in FeedbackStatus
    }
    assert "FeedbackPage" in schemas

    # List filters are part of the contract.
    list_params = {p["name"] for p in spec["paths"]["/feedbacks"]["get"]["parameters"]}
    assert {
        "status",
        "feedback_type",
        "urgency",
        "system_id",
        "module_id",
        "keyword",
    } <= list_params

    # Attachment + comment endpoints and their schemas are declared.
    assert "get" in spec["paths"]["/feedbacks/{feedback_id}/attachments"]
    assert "post" in spec["paths"]["/feedbacks/{feedback_id}/attachments"]
    assert "get" in spec["paths"]["/feedbacks/{feedback_id}/attachments/{file_id}/download"]
    assert "get" in spec["paths"]["/feedbacks/{feedback_id}/comments"]
    assert "post" in spec["paths"]["/feedbacks/{feedback_id}/comments"]
    for schema_name in ("AttachmentOut", "CommentCreate", "CommentOut"):
        assert schema_name in schemas
    # Business attachment metadata must never expose storage_key.
    assert "storage_key" not in schemas["AttachmentOut"]["properties"]
    assert "storage_key" not in schemas["FileMetadata"]["properties"]
    assert "get" in spec["paths"]["/files/{file_id}/download"]
    assert "get" in spec["paths"]["/files/{file_id}/exists"]
    assert "delete" in spec["paths"]["/files/{file_id}"]
    assert "standalone" in spec["paths"]["/files/{file_id}/download"]["get"]["description"]


def _ids_of(session: Session, username: str) -> int:
    user = session.scalar(select(User).where(User.username == username))
    assert user is not None
    return user.id

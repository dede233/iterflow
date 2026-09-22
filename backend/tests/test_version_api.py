from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.entities import (
    OperationLog,
    Permission,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope, UserStatus

SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"

PERMS = {
    "rd.version.view",
    "rd.version.create",
    "rd.version.edit",
    "rd.version.status",
    "rd.requirement.view",
    "rd.requirement.create",
}

Fixture = tuple[TestClient, Session, dict[str, dict[str, str]], dict[str, int]]


@pytest.fixture
def ver_api(tmp_path: Path) -> Iterator[Fixture]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ver-api.db'}", connect_args={"check_same_thread": False}
    )
    for table in (
        User.__table__,
        Role.__table__,
        Permission.__table__,
        UserRole.__table__,
        RolePermission.__table__,
        OperationLog.__table__,
        Requirement.__table__,
        Version.__table__,
        VersionRequirement.__table__,
    ):
        table.create(engine)

    listeners = []
    for model in (User, Role, Permission, OperationLog, Requirement, Version, VersionRequirement):
        counter = iter(range(1, 100000))

        def assign_id(_mapper, _connection, target, *, _counter=counter):
            if target.id is None:
                target.id = next(_counter)

        event.listen(model, "before_insert", assign_id)
        listeners.append((model, assign_id))

    with Session(engine, expire_on_commit=False) as session:
        role_all = Role(code="ALLROLE", name="全域", data_scope=DataScope.ALL)
        role_self = Role(code="SELFROLE", name="本人", data_scope=DataScope.SELF)
        perms = {code: Permission(code=code, name=code) for code in sorted(PERMS)}
        session.add_all([role_all, role_self, *perms.values()])
        session.flush()
        for role in (role_all, role_self):
            for perm in perms.values():
                session.add(RolePermission(role_id=role.id, permission_id=perm.id))

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
        session.add_all([boss, alice, bob])
        session.flush()
        session.add_all(
            [
                UserRole(user_id=boss.id, role_id=role_all.id),
                UserRole(user_id=alice.id, role_id=role_self.id),
                UserRole(user_id=bob.id, role_id=role_self.id),
            ]
        )
        session.commit()

        ids = {"boss": boss.id, "alice": alice.id, "bob": bob.id}
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


def _version(client, headers, **overrides) -> dict:
    body = {"version_no": overrides.pop("version_no", "V1.0.0"), "name": "首个版本"}
    body.update(overrides)
    r = client.post("/api/v1/versions", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _requirement(client, headers, **overrides) -> dict:
    body = {"title": "需求", "requirement_type": "FEATURE", "description": "描述内容"}
    body.update(overrides)
    r = client.post("/api/v1/requirements", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _to_ready(client, headers, version: dict) -> dict:
    rev = version["revision"]
    for target in ("DEVELOPING", "TESTING", "READY"):
        r = client.patch(
            f"/api/v1/versions/{version['id']}/status",
            headers=headers,
            json={"status": target, "revision": rev},
        )
        assert r.status_code == 200, r.text
        rev = r.json()["revision"]
    return client.get(f"/api/v1/versions/{version['id']}", headers=headers).json()


# --------------------------------------------------------------------------- #
# CRUD + revision                                                             #
# --------------------------------------------------------------------------- #
def test_version_crud_and_optimistic_lock(ver_api):
    client, _session, headers, _ids = ver_api
    v = _version(client, headers["alice"], name="A 版本")
    assert v["version_no"] == "V1.0.0"
    assert v["status"] == "PLANNING"
    assert v["revision"] == 1

    page = client.get("/api/v1/versions", headers=headers["alice"]).json()
    assert page["total"] == 1 and {"items", "page", "page_size", "total"} <= page.keys()

    upd = client.patch(
        f"/api/v1/versions/{v['id']}",
        headers=headers["alice"],
        json={"name": "改名", "revision": 1},
    )
    assert upd.status_code == 200 and upd.json()["revision"] == 2

    stale = client.patch(
        f"/api/v1/versions/{v['id']}",
        headers=headers["alice"],
        json={"name": "再改", "revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["data"]["current_revision"] == 2


def test_version_status_machine(ver_api):
    client, _session, headers, _ids = ver_api
    v = _version(client, headers["alice"])
    vid = v["id"]

    def status(target, revision, **extra):
        return client.patch(
            f"/api/v1/versions/{vid}/status",
            headers=headers["alice"],
            json={"status": target, "revision": revision, **extra},
        )

    assert status("READY", 1).status_code == 409  # illegal jump
    assert status("RELEASED", 1).status_code == 422  # not a ManualVersionStatus

    r = status("DEVELOPING", 1)
    assert r.status_code == 200
    r = status("TESTING", r.json()["revision"])
    r = status("READY", r.json()["revision"])
    assert r.status_code == 200 and r.json()["status"] == "READY"
    # READY -> TESTING requires a reason.
    assert status("TESTING", r.json()["revision"]).status_code == 422
    back = status("TESTING", r.json()["revision"], reason="需要回归")
    assert back.status_code == 200 and back.json()["status"] == "TESTING"


# --------------------------------------------------------------------------- #
# requirement relationship                                                    #
# --------------------------------------------------------------------------- #
def test_add_list_and_stats(ver_api):
    client, session, headers, _ids = ver_api
    v = _version(client, headers["alice"])
    req = _requirement(client, headers["alice"], title="R1")

    added = client.post(
        f"/api/v1/versions/{v['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    assert added.status_code == 200, added.text

    # VersionRequirement active + current_version_id + status PLANNED synced.
    rel = session.scalar(
        select(VersionRequirement).where(
            VersionRequirement.version_id == v["id"],
            VersionRequirement.requirement_id == req["id"],
            VersionRequirement.active.is_(True),
        )
    )
    assert rel is not None
    detail = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    assert detail["current_version_id"] == v["id"]
    assert detail["status"] == "PLANNED"

    view = client.get(f"/api/v1/versions/{v['id']}/requirements", headers=headers["alice"]).json()
    assert [r["id"] for r in view["items"]] == [req["id"]]
    assert view["stats"]["total"] == 1
    assert view["stats"]["completed"] == 0
    assert view["stats"]["completion_rate"] == 0.0
    assert view["stats"]["by_status"]["PLANNED"] == 1


def test_add_requirement_already_in_a_version_conflicts(ver_api):
    client, _session, headers, _ids = ver_api
    v1 = _version(client, headers["alice"], version_no="V1.0.0")
    v2 = _version(client, headers["alice"], version_no="V1.0.1")
    req = _requirement(client, headers["alice"])
    first = client.post(
        f"/api/v1/versions/{v1['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    assert first.status_code == 200
    latest = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    # adding to the same version -> 409; adding to another version -> 409 (use move)
    assert (
        client.post(
            f"/api/v1/versions/{v1['id']}/requirements",
            headers=headers["alice"],
            json={"requirement_id": req["id"], "revision": latest["revision"]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/versions/{v2['id']}/requirements",
            headers=headers["alice"],
            json={"requirement_id": req["id"], "revision": latest["revision"]},
        ).status_code
        == 409
    )


def test_remove_requirement(ver_api):
    client, session, headers, _ids = ver_api
    v = _version(client, headers["alice"])
    req = _requirement(client, headers["alice"])
    client.post(
        f"/api/v1/versions/{v['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    latest = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    removed = client.request(
        "DELETE",
        f"/api/v1/versions/{v['id']}/requirements/{req['id']}",
        headers=headers["alice"],
        json={"revision": latest["revision"], "reason": "移出"},
    )
    assert removed.status_code == 200, removed.text
    detail = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    assert detail["current_version_id"] is None
    rel = session.scalar(
        select(VersionRequirement).where(
            VersionRequirement.requirement_id == req["id"], VersionRequirement.active.is_(True)
        )
    )
    assert rel is None


def test_move_requirement_closes_old_and_opens_new(ver_api):
    client, session, headers, _ids = ver_api
    v1 = _version(client, headers["alice"], version_no="V1.0.0")
    v2 = _version(client, headers["alice"], version_no="V1.0.1")
    req = _requirement(client, headers["alice"])
    client.post(
        f"/api/v1/versions/{v1['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    latest = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    moved = client.post(
        f"/api/v1/versions/{v2['id']}/requirements/move",
        headers=headers["alice"],
        json={
            "requirement_id": req["id"],
            "revision": latest["revision"],
            "reason": "迁移到补丁版本",
        },
    )
    assert moved.status_code == 200, moved.text
    detail = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    assert detail["current_version_id"] == v2["id"]
    active = session.scalars(
        select(VersionRequirement).where(
            VersionRequirement.requirement_id == req["id"], VersionRequirement.active.is_(True)
        )
    ).all()
    assert len(active) == 1 and active[0].version_id == v2["id"]
    closed = session.scalar(
        select(VersionRequirement).where(
            VersionRequirement.requirement_id == req["id"],
            VersionRequirement.version_id == v1["id"],
            VersionRequirement.active.is_(False),
        )
    )
    assert closed is not None and closed.removed_reason == "迁移到补丁版本"


def test_move_stale_revision_rolls_back(ver_api):
    client, session, headers, _ids = ver_api
    v1 = _version(client, headers["alice"], version_no="V1.0.0")
    v2 = _version(client, headers["alice"], version_no="V1.0.1")
    req = _requirement(client, headers["alice"])
    client.post(
        f"/api/v1/versions/{v1['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    resp = client.post(
        f"/api/v1/versions/{v2['id']}/requirements/move",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": 999, "reason": "stale move"},
    )
    assert resp.status_code == 409
    # nothing changed: still active in v1, no relation to v2
    active = session.scalars(
        select(VersionRequirement).where(
            VersionRequirement.requirement_id == req["id"], VersionRequirement.active.is_(True)
        )
    ).all()
    assert len(active) == 1 and active[0].version_id == v1["id"]
    assert (
        session.scalar(select(VersionRequirement).where(VersionRequirement.version_id == v2["id"]))
        is None
    )


# --------------------------------------------------------------------------- #
# freeze (READY / RELEASED / CANCELED)                                        #
# --------------------------------------------------------------------------- #
def test_ready_version_is_frozen_for_requirement_changes(ver_api):
    client, _session, headers, _ids = ver_api
    v = _version(client, headers["alice"])
    req = _requirement(client, headers["alice"])
    ready = _to_ready(client, headers["alice"], v)
    assert ready["status"] == "READY"
    # add -> 409
    assert (
        client.post(
            f"/api/v1/versions/{v['id']}/requirements",
            headers=headers["alice"],
            json={"requirement_id": req["id"], "revision": req["revision"]},
        ).status_code
        == 409
    )
    # move into a READY version -> 409
    assert (
        client.post(
            f"/api/v1/versions/{v['id']}/requirements/move",
            headers=headers["alice"],
            json={"requirement_id": req["id"], "revision": req["revision"], "reason": "冻结测试"},
        ).status_code
        == 409
    )


# --------------------------------------------------------------------------- #
# data scope / IDOR                                                           #
# --------------------------------------------------------------------------- #
def test_self_scope_isolation(ver_api):
    client, _session, headers, _ids = ver_api
    alice_v = _version(client, headers["alice"], name="alice-version")
    assert (
        client.get(f"/api/v1/versions/{alice_v['id']}", headers=headers["bob"]).status_code == 404
    )
    assert (
        client.get(
            f"/api/v1/versions/{alice_v['id']}/requirements", headers=headers["bob"]
        ).status_code
        == 404
    )
    bob_req = _requirement(client, headers["bob"])
    assert (
        client.post(
            f"/api/v1/versions/{alice_v['id']}/requirements",
            headers=headers["bob"],
            json={"requirement_id": bob_req["id"], "revision": bob_req["revision"]},
        ).status_code
        == 404
    )
    # ALL boss can access.
    assert (
        client.get(f"/api/v1/versions/{alice_v['id']}", headers=headers["boss"]).status_code == 200
    )


# --------------------------------------------------------------------------- #
# DB uniqueness: one active version per requirement                            #
# --------------------------------------------------------------------------- #
def test_one_active_version_per_requirement_db_constraint(ver_api):
    client, session, headers, _ids = ver_api
    v1 = _version(client, headers["alice"], version_no="V1.0.0")
    v2 = _version(client, headers["alice"], version_no="V1.0.1")
    req = _requirement(client, headers["alice"])
    session.add(VersionRequirement(version_id=v1["id"], requirement_id=req["id"], active=True))
    session.commit()
    session.add(VersionRequirement(version_id=v2["id"], requirement_id=req["id"], active=True))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --------------------------------------------------------------------------- #
# audit                                                                        #
# --------------------------------------------------------------------------- #
def test_audit_actions(ver_api):
    client, session, headers, _ids = ver_api
    v1 = _version(client, headers["alice"], version_no="V1.0.0")
    v2 = _version(client, headers["alice"], version_no="V1.0.1")
    client.patch(
        f"/api/v1/versions/{v1['id']}", headers=headers["alice"], json={"name": "改", "revision": 1}
    )
    client.patch(
        f"/api/v1/versions/{v1['id']}/status",
        headers=headers["alice"],
        json={"status": "DEVELOPING", "revision": 2},
    )
    req = _requirement(client, headers["alice"])
    client.post(
        f"/api/v1/versions/{v1['id']}/requirements",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": req["revision"]},
    )
    latest = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    client.post(
        f"/api/v1/versions/{v2['id']}/requirements/move",
        headers=headers["alice"],
        json={"requirement_id": req["id"], "revision": latest["revision"], "reason": "迁移"},
    )
    lt = client.get(f"/api/v1/requirements/{req['id']}", headers=headers["alice"]).json()
    client.request(
        "DELETE",
        f"/api/v1/versions/{v2['id']}/requirements/{req['id']}",
        headers=headers["alice"],
        json={"revision": lt["revision"], "reason": "移出"},
    )

    actions = set(
        session.scalars(
            select(OperationLog.action).where(OperationLog.entity_type == "VERSION")
        ).all()
    )
    assert {
        "CREATE",
        "UPDATE",
        "STATUS_CHANGE",
        "VERSION_REQUIREMENT_ADD",
        "VERSION_REQUIREMENT_MOVE",
        "VERSION_REQUIREMENT_REMOVE",
    } <= actions
    # UPDATE audit carries real before/after (not just revision).
    upd = session.scalar(
        select(OperationLog).where(
            OperationLog.entity_type == "VERSION", OperationLog.action == "UPDATE"
        )
    )
    assert upd.before_data.get("name") == "首个版本" and upd.after_data.get("name") == "改"


# --------------------------------------------------------------------------- #
# OpenAPI contract                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("spec_name", ["openapi-v1.5.yaml", "需求与版本管理系统_V1.5_OpenAPI.yaml"])
def test_openapi_declares_version_contract(spec_name):
    spec = yaml.safe_load((SPEC_DIR / spec_name).read_text(encoding="utf-8"))
    p = spec["paths"]
    assert "get" in p["/versions"] and "post" in p["/versions"]
    assert "get" in p["/versions/{version_id}"] and "patch" in p["/versions/{version_id}"]
    assert "patch" in p["/versions/{version_id}/status"]
    assert "get" in p["/versions/{version_id}/requirements"]
    assert "post" in p["/versions/{version_id}/requirements"]
    assert "post" in p["/versions/{version_id}/requirements/move"]
    assert "delete" in p["/versions/{version_id}/requirements/{requirement_id}"]
    schemas = spec["components"]["schemas"]
    for name in ("VersionOut", "VersionPage", "VersionRequirementsOut", "AddRequirementRequest"):
        assert name in schemas
    # The retired requirement-centric move endpoint must be gone.
    assert "/requirements/{requirement_id}/move-version" not in p

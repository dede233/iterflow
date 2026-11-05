"""The same scope/label queries against each task-owned isolated database."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import (
    Permission,
    Requirement,
    RequirementParticipant,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
    VersionRequirement,
)
from app.models.enums import DataScope


def exercise_filter_options(fixture):
    client, engine, _admin_id, _admin_headers = fixture
    with Session(engine, expire_on_commit=False) as db:
        permissions = {}
        for code in ("rd.requirement.view", "rd.version.view"):
            permission = db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code, name=code)
                db.add(permission)
                db.flush()
            permissions[code] = permission.id
        people = {}
        for name in ("self", "other", "disabled", "removed", "reader"):
            user = User(
                username=f"filter-{name}",
                display_name="Alpha%_\\Name" if name == "disabled" else f"filter-{name}",
                password_hash="unused",
                must_change_password=False,
                status="DISABLED" if name == "disabled" else "ACTIVE",
            )
            db.add(user)
            db.flush()
            people[name] = user
        for name, scope, codes in (
            ("self", DataScope.SELF, set(permissions)),
            ("reader", DataScope.ALL, {"rd.requirement.view"}),
        ):
            role = Role(code=f"FILTER_{name.upper()}", name=name, data_scope=scope)
            db.add(role)
            db.flush()
            db.add(UserRole(user_id=people[name].id, role_id=role.id))
            for code in codes:
                db.add(RolePermission(role_id=role.id, permission_id=permissions[code]))
        versions = {}
        for name, creator, owner in (
            ("可见", "self", "disabled"),
            ("SECRET", "other", "other"),
            ("deleted-only", "self", "other"),
        ):
            item = Version(
                version_no=f"FILTER-{name}",
                name=name,
                created_by=people[creator].id,
                owner_id=people[owner].id,
            )
            db.add(item)
            db.flush()
            versions[name] = item
        requirements = {}
        for name, creator, target in (
            ("visible", "self", "可见"),
            ("masked", "self", "SECRET"),
            ("hidden", "other", "SECRET"),
            ("deleted", "self", "deleted-only"),
        ):
            item = Requirement(
                requirement_no=f"FILTER-{name}",
                title=f"筛选验收{name}",
                description="隔离筛选验收内容",
                requirement_type="FEATURE",
                created_by=people[creator].id,
                deleted_at=datetime.now(UTC) if name == "deleted" else None,
            )
            if engine.dialect.name != "mysql":
                item.current_version_id = versions[target].id
            db.add(item)
            db.flush()
            db.add(
                VersionRequirement(
                    version_id=versions[target].id, requirement_id=item.id, active=True
                )
            )
            db.add(
                RequirementParticipant(
                    requirement_id=item.id, user_id=people[creator].id, role="CONFIRM"
                )
            )
            requirements[name] = item
        for name, active, role in (
            ("disabled", True, "DEVELOP"),
            ("disabled", True, "ACCEPT"),
            ("removed", False, "DEVELOP"),
        ):
            db.add(
                RequirementParticipant(
                    requirement_id=requirements["visible"].id,
                    user_id=people[name].id,
                    role=role,
                    active=active,
                )
            )
        db.commit()
        uid = {name: user.id for name, user in people.items()}
        vid = {name: version.id for name, version in versions.items()}

    def get(path, user="self", **params):
        response = client.get(
            f"/api/v1/{path}",
            headers={"Authorization": "Bearer " + create_access_token(uid[user])},
            params=params,
        )
        assert response.status_code == 200, response.text
        return response.json()

    participants = "requirements/filter-options/participants"
    version_options = "requirements/filter-options/versions"
    owners = "versions/filter-options/owners"
    result = get(participants)
    assert result["total"] == 2
    assert {item["id"]: item["label"] for item in result["items"]} == {
        uid["self"]: "filter-self",
        uid["disabled"]: "Alpha%_\\Name(已停用)",
    }
    assert get(participants, selected_id=uid["other"])["items"] == []
    assert get(participants, selected_id=uid["removed"])["items"] == []
    assert get(participants, "reader")["total"] == 3
    for keyword in ("%", "_", "\\", " alpha%_\\name "):
        assert get(participants, keyword=keyword)["total"] == 1
    first, second = get(participants, page_size=1), get(participants, page_size=1, page=2)
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    result = get(version_options)
    assert result["total"] == 2
    assert {item["id"]: item["label"] for item in result["items"]} == {
        vid["可见"]: "FILTER-可见 · 可见",
        vid["SECRET"]: f"版本 #{vid['SECRET']}(无查看权限)",
    }
    assert get(version_options, keyword="SECRET")["total"] == 0
    assert get(version_options, selected_id=vid["deleted-only"])["total"] == 0
    reader_versions = get(version_options, "reader")
    assert reader_versions["total"] == 2
    assert all(
        item["label"] == f"版本 #{item['id']}(无查看权限)" for item in reader_versions["items"]
    )
    assert {item["id"] for item in get(owners)["items"]} == {uid["disabled"], uid["other"]}
    assert get(owners, selected_id=uid["removed"])["items"] == []

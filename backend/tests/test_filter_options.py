from datetime import UTC, datetime

import pytest
from filter_options_acceptance import exercise_filter_options
from sqlalchemy import select
from test_entity_actions import actions_api as actions_api
from test_entity_actions import req

from app.core.security import create_access_token
from app.models.entities import (
    Permission,
    RequirementParticipant,
    Role,
    RolePermission,
    User,
    Version,
)

PARTICIPANTS = "/api/v1/requirements/filter-options/participants"
VERSIONS = "/api/v1/requirements/filter-options/versions"
OWNERS = "/api/v1/versions/filter-options/owners"


def test_shared_dialect_acceptance_uses_isolated_data(actions_api):
    client, db, headers, users = actions_api
    exercise_filter_options((client, db.get_bind(), users["boss"].id, headers["boss"]))


@pytest.fixture
def options_api(actions_api):
    client, db, headers, users = actions_api
    permission = Permission(code="rd.version.view", name="版本查看")
    db.add(permission)
    db.flush()
    for role in db.scalars(select(Role).where(Role.code.in_(["ALLTEST", "SELFTEST"]))):
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    for name in ("disabled", "hidden", "removed", "deleted", "outsider"):
        user = User(
            username=name,
            display_name=name,
            password_hash="unused",
            must_change_password=False,
            status="DISABLED" if name == "disabled" else "ACTIVE",
        )
        db.add(user)
        db.flush()
        users[name] = user
    headers["outsider"] = {"Authorization": "Bearer " + create_access_token(users["outsider"].id)}
    db.commit()
    return client, db, headers, users


def actor(db, requirement, person, *, active=True, role="DEVELOP"):
    db.add(
        RequirementParticipant(
            requirement_id=requirement.id, user_id=person.id, role=role, active=active
        )
    )
    db.commit()


def version(db, creator, name, owner=None):
    item = Version(
        version_no="V-" + name,
        name=name,
        created_by=creator.id,
        owner_id=owner.id if owner else None,
    )
    db.add(item)
    db.commit()
    return item


@pytest.mark.parametrize("path", [PARTICIPANTS, VERSIONS, OWNERS])
def test_options_require_parent_read_permission(options_api, path):
    client, _db, headers, _users = options_api
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers["outsider"]).status_code == 403


def test_participants_are_visible_active_relationships_including_disabled_users(options_api):
    client, db, headers, users = options_api
    visible = req(db, users["alice"], "visible")
    actor(db, visible, users["disabled"])
    actor(db, visible, users["disabled"], role="ACCEPT")
    actor(db, visible, users["removed"], active=False)
    hidden = req(db, users["bob"], "hidden")
    actor(db, hidden, users["hidden"])
    deleted = req(db, users["alice"], "deleted", deleted_at=datetime.now(UTC))
    actor(db, deleted, users["deleted"])
    response = client.get(PARTICIPANTS, headers=headers["alice"])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [
            {"id": users["alice"].id, "label": "alice"},
            {"id": users["disabled"].id, "label": "disabled(已停用)"},
        ],
        "total": 2,
        "page": 1,
        "page_size": 20,
    }
    assert not db.dirty and not db.new
    for user in ("hidden", "removed", "deleted"):
        result = client.get(
            PARTICIPANTS, headers=headers["alice"], params={"selected_id": users[user].id}
        ).json()
        assert result["items"] == [] and result["total"] == 0
    # Read-only ALL users can filter without edit or user-administration permission.
    assert client.get(PARTICIPANTS, headers=headers["reader"]).json()["total"] == 4


def test_participant_visibility_tracks_current_membership_and_permission_revocation(options_api):
    client, db, headers, users = options_api
    shared = req(db, users["bob"], "shared")
    actor(db, shared, users["alice"])
    assert client.get(PARTICIPANTS, headers=headers["alice"]).json()["total"] == 2
    db.get(RequirementParticipant, (shared.id, users["alice"].id, "DEVELOP")).active = False
    db.commit()
    assert client.get(PARTICIPANTS, headers=headers["alice"]).json()["items"] == []
    db.scalar(select(Role).where(Role.code == "SELFTEST")).enabled = False
    db.commit()
    assert client.get(PARTICIPANTS, headers=headers["alice"]).status_code == 403


def test_person_search_escapes_wildcards_and_paginates_unique_labels(options_api):
    client, db, headers, users = options_api
    users["disabled"].display_name = "Alpha%_\\Name"
    visible = req(db, users["alice"], "search")
    actor(db, visible, users["disabled"])
    actor(db, visible, users["disabled"], role="ACCEPT")
    for keyword in (" alpha%_\\name ", "%", "_", "\\"):
        result = client.get(PARTICIPANTS, headers=headers["alice"], params={"keyword": keyword})
        assert result.status_code == 200
        assert result.json()["total"] == 1
        assert result.json()["items"][0]["id"] == users["disabled"].id
    first = client.get(PARTICIPANTS, headers=headers["alice"], params={"page_size": 1}).json()
    second = client.get(
        PARTICIPANTS, headers=headers["alice"], params={"page_size": 1, "page": 2}
    ).json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert (
        client.get(
            PARTICIPANTS,
            headers=headers["alice"],
            params={"selected_id": users["disabled"].id, "keyword": "alice"},
        ).json()["total"]
        == 0
    )


def test_requirement_versions_mask_hidden_labels_and_do_not_search_hidden_names(options_api):
    client, db, headers, users = options_api
    readable = version(db, users["alice"], "visible")
    private = version(db, users["bob"], "SECRET")
    unrelated = version(db, users["alice"], "unused")
    req(db, users["alice"], "visible", current_version_id=readable.id)
    req(db, users["alice"], "duplicate", current_version_id=readable.id)
    req(db, users["alice"], "private", current_version_id=private.id)
    req(db, users["bob"], "hidden", current_version_id=unrelated.id)
    result = client.get(VERSIONS, headers=headers["alice"]).json()
    assert result["total"] == 2
    assert {item["id"]: item["label"] for item in result["items"]} == {
        readable.id: "V-visible · visible",
        private.id: f"版本 #{private.id}(无查看权限)",
    }
    for params in ({"keyword": "SECRET"}, {"selected_id": unrelated.id}):
        assert client.get(VERSIONS, headers=headers["alice"], params=params).json()["total"] == 0
    # Reader has Requirement ALL but no Version permission: only association IDs are exposed.
    reader = client.get(VERSIONS, headers=headers["reader"]).json()
    assert reader["total"] == 3
    assert all(item["label"] == f"版本 #{item['id']}(无查看权限)" for item in reader["items"])
    assert (
        client.get(VERSIONS, headers=headers["reader"], params={"keyword": "SECRET"}).json()[
            "items"
        ]
        == []
    )
    deleted = req(db, users["alice"], "deleted", current_version_id=unrelated.id)
    deleted.deleted_at = datetime.now(UTC)
    db.commit()
    assert (
        client.get(VERSIONS, headers=headers["alice"], params={"selected_id": unrelated.id}).json()[
            "items"
        ]
        == []
    )


def test_version_owners_use_version_scope_without_exposing_unused_accounts(options_api):
    client, db, headers, users = options_api
    version(db, users["alice"], "first", users["disabled"])
    version(db, users["alice"], "second", users["disabled"])
    version(db, users["bob"], "private", users["hidden"])
    version(db, users["bob"], "assigned", users["alice"])
    result = client.get(OWNERS, headers=headers["alice"])
    assert result.status_code == 200
    assert result.json()["items"] == [
        {"id": users["alice"].id, "label": "alice"},
        {"id": users["disabled"].id, "label": "disabled(已停用)"},
    ]
    assert result.json()["total"] == 2
    assert (
        client.get(
            OWNERS, headers=headers["alice"], params={"selected_id": users["hidden"].id}
        ).json()["items"]
        == []
    )
    assert client.get(OWNERS, headers=headers["reader"]).status_code == 403
    assert client.get(OWNERS, headers=headers["boss"]).json()["total"] == 3


@pytest.mark.parametrize("path", [PARTICIPANTS, VERSIONS, OWNERS])
@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 101}, {"selected_id": 0}, {"keyword": "a" * 101}]
)
def test_filter_option_query_bounds(options_api, path, params):
    client, _db, headers, _users = options_api
    assert client.get(path, headers=headers["alice"], params=params).status_code == 422

from base64 import b64decode
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.entities import FileObject, OperationLog, Permission, Role, User, UserRole
from app.models.enums import UserStatus

PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aGQAAAAASUVORK5CYII="
)
PATH = "/api/v1/ad-productions"
FIELDS = {"work_date": "2026-11-26", "content": "中央公园店海报设计", "issuer": "客服 张三"}


def publication_fields(receiver_id, **overrides):
    return {**FIELDS, "title": "门店广告制作", "receiver_id": receiver_id, **overrides}


def form(fields, *images, removals=()):
    return [
        *((name, (None, str(value))) for name, value in fields.items()),
        *(("remove_image_ids", (None, str(file_id))) for file_id in removals),
        *(("images", image) for image in images),
    ]


def user_with_scope(client, engine, admin, *, name, permissions):
    catalog = client.get("/api/v1/roles/permissions", headers=admin).json()
    assert permissions <= {p["code"] for p in catalog}
    role = client.post(
        "/api/v1/roles",
        headers=admin,
        json={
            "code": name.upper(),
            "name": name,
            "data_scope": "SELF",
            "permission_ids": [p["id"] for p in catalog if p["code"] in permissions],
        },
    )
    assert role.status_code == 200, role.text
    return user_with_role(client, engine, admin, name=name, role_id=role.json()["id"])


def user_with_role(client, engine, admin, *, name, role_id, historical_assignment=False):
    user = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "username": name,
            "display_name": name,
            "password": "Fresh-disposable-ad-account-password!",
            "role_ids": [] if historical_assignment else [role_id],
        },
    )
    assert user.status_code == 200, user.text
    user_id = user.json()["id"]
    with Session(engine) as session:
        session.get(User, user_id).must_change_password = False
        if historical_assignment:
            # Model an existing membership from before new assignments were retired.
            role = session.get(Role, role_id)
            assert role.is_system and role.code in {
                "AD_PRODUCTION_CREATOR",
                "AD_PRODUCTION_COMPLETER",
            }
            session.add(UserRole(user_id=user_id, role_id=role_id))
        session.commit()
    return user_id, {"Authorization": "Bearer " + create_access_token(user_id)}


def create_ad_receiver(
    client, engine, admin, *, name="assigned_ad_designer", historical_assignment=False
):
    code = "AD_PRODUCTION_COMPLETER" if historical_assignment else "DESIGNER"
    with Session(engine) as session:
        role_id = session.scalar(select(Role.id).where(Role.code == code))
    return user_with_role(
        client,
        engine,
        admin,
        name=name,
        role_id=role_id,
        historical_assignment=historical_assignment,
    )


def exercise_ad_production(api):
    client, engine, _, admin = api
    view = "ops.ad_production.view"
    creator_id, maker = user_with_scope(
        client,
        engine,
        admin,
        name="ad_maker",
        permissions={view, "ops.ad_production.create", "ops.ad_production.edit", "sys.audit.view"},
    )
    _, viewer = user_with_scope(
        client, engine, admin, name="ad_viewer", permissions={view, "sys.audit.view"}
    )
    _, outsider = user_with_scope(
        client,
        engine,
        admin,
        name="ad_outside",
        permissions={"sys.audit.view", "sys.file.download"},
    )
    receiver_id, _ = create_ad_receiver(client, engine, admin)
    publication = publication_fields(receiver_id)
    assert client.get(PATH).status_code == 401
    assert client.get(PATH, headers=outsider).status_code == 403
    assert client.post(PATH, headers=viewer, files=form(publication)).status_code == 403

    created = client.post(
        PATH, headers=maker, files=form(publication, ("poster.png", PNG, "image/png"))
    )
    assert created.status_code == 201, created.text
    record = created.json()
    ad_id = record["id"]
    file_id = record["images"][0]["file_id"]
    detail = f"{PATH}/{ad_id}"
    preview = f"{detail}/images/{file_id}"
    assert record["status"] == "NOT_STARTED" and record["revision"] == 1
    assert record["created_by"] == creator_id and record["issuer"] == FIELDS["issuer"]
    assert client.get(detail, headers=viewer).status_code == 404
    assert client.get(preview, headers=viewer).status_code == 404
    assert client.get(preview, headers=outsider).status_code == 403
    assert client.get(f"/api/v1/files/{file_id}/download", headers=admin).status_code == 404
    image = client.get(preview, headers=maker)
    assert image.content == PNG and image.headers["content-type"] == "image/png"
    assert image.headers["x-content-type-options"] == "nosniff"

    another = client.post(
        PATH,
        headers=admin,
        files=form({**publication, "work_date": "2026-11-24", "content": "另一张海报"}),
    )
    assert another.status_code == 201, another.text
    assert client.get(PATH, headers=maker).json()["total"] == 1
    assert client.get(PATH, headers=admin).json()["total"] == 2
    assert client.get(PATH, headers=viewer).json()["total"] == 0
    filtered = client.get(
        PATH,
        headers=admin,
        params={"date_from": "2026-11-26", "keyword": "客服", "status": "NOT_STARTED"},
    )
    assert [item["id"] for item in filtered.json()["items"]] == [ad_id]

    changes = {**FIELDS, "status": "SHIPPING", "revision": 1}
    bad = client.patch(
        detail,
        headers=maker,
        files=form(
            changes,
            ("will-roll-back.png", PNG, "image/png"),
            ("not-a-png.png", b"invalid image bytes", "image/png"),
            removals=[file_id],
        ),
    )
    assert bad.status_code == 422, bad.text
    assert client.get(detail, headers=maker).json() == record
    storage = Path(get_settings().local_storage_path)
    assert sum(path.is_file() for path in storage.rglob("*")) == 1
    saved = client.patch(
        detail,
        headers=maker,
        files=form(changes, ("final.png", PNG, "image/png"), removals=[file_id]),
    )
    assert saved.status_code == 200, saved.text
    updated = saved.json()
    assert updated["status"] == "SHIPPING" and updated["revision"] == 2
    assert [image["original_name"] for image in updated["images"]] == ["final.png"]
    assert client.get(preview, headers=maker).status_code == 404
    assert client.get(f"/api/v1/files/{file_id}/download", headers=admin).status_code == 404
    stale = client.patch(
        detail, headers=maker, files=form(changes, ("stale.png", PNG, "image/png"))
    )
    assert stale.status_code == 409 and stale.json()["data"]["current_revision"] == 2
    assert client.get(detail, headers=maker).json() == updated
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(FileObject)) == 2

    filters = {"entity_type": "AD_PRODUCTION", "entity_id": ad_id}
    audits = client.get("/api/v1/audits", headers=maker, params=filters)
    assert [item["action"] for item in audits.json()["items"]] == ["UPDATE", "CREATE"]
    assert client.get("/api/v1/audits", headers=viewer, params=filters).json()["total"] == 0
    assert client.get("/api/v1/audits", headers=outsider, params=filters).status_code == 403


def exercise_ad_production_people(api):
    client, engine, _, admin = api
    with Session(engine) as session:
        roles = dict(session.execute(select(Role.code, Role.id)).all())
    creator_id, creator = user_with_role(
        client,
        engine,
        admin,
        name="ad_submitter",
        role_id=roles["AD_PRODUCTION_CREATOR"],
        historical_assignment=True,
    )
    receiver_id, completer = user_with_role(
        client,
        engine,
        admin,
        name="ad_completer",
        role_id=roles["AD_PRODUCTION_COMPLETER"],
        historical_assignment=True,
    )
    finisher_id, finisher = user_with_role(
        client, engine, admin, name="ad_designer_b", role_id=roles["DESIGNER"]
    )
    inactive_id, _ = user_with_role(
        client, engine, admin, name="ad_designer_inactive", role_id=roles["DESIGNER"]
    )
    _, member = user_with_role(client, engine, admin, name="ad_member", role_id=roles["MEMBER"])
    with Session(engine) as session:
        session.get(User, inactive_id).status = UserStatus.DISABLED
        session.add(UserRole(user_id=finisher_id, role_id=roles["AD_PRODUCTION_COMPLETER"]))
        session.commit()
    creator_profile = client.get("/api/v1/auth/me", headers=creator).json()
    assert creator_profile["data_scope"] == "SELF"
    assert set(creator_profile["permission_codes"]) == {
        "ops.ad_production.view",
        "ops.ad_production.create",
        "ops.merchant_ad.view",
        "ops.merchant_ad.create",
    }
    completer_profile = client.get("/api/v1/auth/me", headers=completer).json()
    assert completer_profile["data_scope"] == "SELF"
    assert set(completer_profile["permission_codes"]) == {
        "ops.ad_production.view",
        "ops.ad_production.edit",
        "ops.merchant_ad.view",
        "ops.merchant_ad.edit",
    }
    options = f"{PATH}/designer-options"
    assert client.get(options, headers=member).status_code == 403
    options_response = client.get(options, headers=creator)
    assert options_response.status_code == 200, options_response.text
    assert options_response.json() == [
        {"id": receiver_id, "display_name": "ad_completer"},
        {"id": finisher_id, "display_name": "ad_designer_b"},
    ]
    publication = publication_fields(receiver_id)
    assert client.post(PATH, headers=completer, files=form(publication)).status_code == 403
    blocked = client.post(
        PATH,
        headers=creator,
        files=form({**publication, "status": "COMPLETED", "completed_by_id": receiver_id}),
    )
    assert blocked.status_code == 403, blocked.text
    for invalid in (creator_id, inactive_id):
        assert (
            client.post(
                PATH, headers=creator, files=form({**publication, "receiver_id": invalid})
            ).status_code
            == 422
        )
    assert (
        client.post(
            PATH, headers=creator, files=form({**publication, "completed_by_id": finisher_id})
        ).status_code
        == 422
    )
    assert client.get(PATH, headers=creator).json()["total"] == 0

    legacy = client.post(
        PATH,
        headers=admin,
        files=form(publication_fields(finisher_id, status="COMPLETED")),
    )
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["completed_by_id"] is None
    created = client.post(PATH, headers=creator, files=form(publication))
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["receiver_display_name"] == "ad_completer"
    assert record["completed_by_id"] is None
    assert record["created_by"] == creator_id
    detail = f"{PATH}/{record['id']}"
    assert client.get(detail, headers=completer).status_code == 200
    assert client.get(PATH, headers=completer).json()["total"] == 1
    assert client.get(detail, headers=finisher).status_code == 404
    completion = {**FIELDS, "revision": 1, "status": "COMPLETED", "completed_by_id": finisher_id}
    assert client.patch(detail, headers=creator, files=form(completion)).status_code == 403
    assert client.patch(detail, headers=finisher, files=form(completion)).status_code == 404
    saved = client.patch(detail, headers=completer, files=form(completion))
    assert saved.status_code == 200, saved.text
    assert saved.json()["receiver_id"] == receiver_id
    assert saved.json()["completed_by_id"] == finisher_id
    assert saved.json()["completed_by_display_name"] == "ad_designer_b"
    assert client.get(detail, headers=finisher).status_code == 200
    assert client.patch(detail, headers=completer, files=form(completion)).status_code == 409
    audit = client.get(
        "/api/v1/audits",
        headers=admin,
        params={"entity_type": "AD_PRODUCTION", "entity_id": record["id"]},
    ).json()["items"]
    assert audit[0]["after"]["completed_by_id"] == finisher_id
    assert audit[1]["after"]["receiver_id"] == receiver_id

    with Session(engine) as session:
        session.get(User, receiver_id).status = UserStatus.DISABLED
        session.commit()
    reopened = client.patch(
        detail,
        headers=finisher,
        files=form({**FIELDS, "revision": 2, "status": "IN_PROGRESS"}),
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["completed_by_id"] is None
    assert reopened.json()["receiver_id"] == receiver_id
    assert reopened.json()["receiver_display_name"] == "ad_completer"
    assert client.get(detail, headers=finisher).status_code == 404
    cleared = client.patch(
        detail,
        headers=admin,
        files=form({**FIELDS, "revision": 3, "status": "IN_PROGRESS", "receiver_id": 0}),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["receiver_id"] is None


def exercise_ad_production_people_migration(api):
    client, engine, admin_id, admin = api
    is_mysql = engine.dialect.name == "mysql"
    config_file = "alembic-mysql.ini" if is_mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / config_file))
    prior = "mysql57_0020" if is_mysql else "0022_feedback_ad_rich_text"
    command.downgrade(config, prior)
    assert "receiver_id" not in {
        column["name"] for column in inspect(engine).get_columns("ops_ad_production")
    }
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO ops_ad_production "
                "(id, work_date, content, issuer, status, created_at, created_by, "
                "updated_at, revision) "
                "VALUES (49, '2026-11-24', '历史海报', '旧下发人', 'COMPLETED', "
                "CURRENT_TIMESTAMP, :admin_id, CURRENT_TIMESTAMP, 1)"
            ),
            {"admin_id": admin_id},
        )
    command.upgrade(config, "head")
    detail = f"{PATH}/49"
    migrated = client.get(detail, headers=admin).json()
    assert migrated["content"] == "历史海报" and migrated["status"] == "COMPLETED"
    assert migrated["receiver_id"] is None and migrated["completed_by_id"] is None
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Role).where(Role.code == "AD_PRODUCTION_CREATOR")
            )
            == 1
        )
        design_role = session.scalar(select(Role.id).where(Role.code == "DESIGNER"))
    designer_id, _ = user_with_role(
        client, engine, admin, name="migration_ad_designer", role_id=design_role
    )
    changed = client.patch(
        detail,
        headers=admin,
        files=form(
            {**FIELDS, "revision": 1, "status": "COMPLETED", "completed_by_id": designer_id}
        ),
    )
    assert changed.status_code == 200, changed.text
    people_head = "mysql57_0021" if is_mysql else "0023_ad_production_people"
    command.downgrade(config, people_head)
    with pytest.raises(RuntimeError, match=r"(?:[Dd]owngrade refused|[Rr]efus.*downgrade)"):
        command.downgrade(config, prior)
    with engine.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == people_head
    command.upgrade(config, "head")
    assert client.get(detail, headers=admin).json()["completed_by_id"] == designer_id


def exercise_ad_production_role_upgrade(api):
    client, engine, _, admin = api
    is_mysql = engine.dialect.name == "mysql"
    config_file = "alembic-mysql.ini" if is_mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / config_file))
    prior = "mysql57_0021" if is_mysql else "0023_ad_production_people"
    head = "mysql57_0022" if is_mysql else "0024_ad_production_roles"
    codes = {"AD_PRODUCTION_CREATOR", "AD_PRODUCTION_COMPLETER"}
    with Session(engine) as session:
        roles = {
            role.code: role for role in session.scalars(select(Role).where(Role.code.in_(codes)))
        }
        assert set(roles) == codes
        creator_id = roles["AD_PRODUCTION_CREATOR"].id
        completer_id = roles["AD_PRODUCTION_COMPLETER"].id
        assert roles["AD_PRODUCTION_CREATOR"].name == "制作需求发布人"
        assert roles["AD_PRODUCTION_COMPLETER"].name == "制作需求完成人"
    user_id, creator = user_with_role(
        client,
        engine,
        admin,
        name="previous_ad_creator",
        role_id=creator_id,
        historical_assignment=True,
    )
    command.downgrade(config, prior)
    with Session(engine) as session:
        publisher = session.get(Role, creator_id)
        publisher.name = "广告制作提交人"
        old_revision = publisher.revision
        session.get(Role, completer_id).is_system = False
        session.commit()
    with pytest.raises(RuntimeError, match="AD_PRODUCTION_COMPLETER"):
        command.upgrade(config, head)
    with Session(engine) as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == prior
        assert session.get(Role, creator_id).name == "广告制作提交人"
        session.get(Role, completer_id).is_system = True
        session.commit()
    command.upgrade(config, head)
    command.downgrade(config, prior)
    command.upgrade(config, head)
    with Session(engine) as session:
        publisher = session.get(Role, creator_id)
        assert publisher.name == "广告制作发布人" and publisher.revision == old_revision + 1
        assert session.get(UserRole, (user_id, creator_id)) is not None
        assert session.get(Role, completer_id).name == "广告制作完成人"
        audit_count = session.scalar(
            select(func.count())
            .select_from(OperationLog)
            .where(
                OperationLog.entity_type == "ROLE",
                OperationLog.action == "ROLE_UPDATE",
                OperationLog.entity_id == creator_id,
                OperationLog.request_id == "migration-ad-production-roles-v1",
            )
        )
        assert audit_count == 2  # initial migration plus one replay after restoring the old name
    command.upgrade(config, "head")
    receiver_id, _ = create_ad_receiver(client, engine, admin)
    assert (
        client.post(PATH, headers=creator, files=form(publication_fields(receiver_id))).status_code
        == 201
    )


def exercise_material_production_names_migration(api):
    client, engine, _, admin = api
    mysql = engine.dialect.name == "mysql"
    config_file = "alembic-mysql.ini" if mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / config_file))
    previous = "mysql57_0023" if mysql else "0025_ad_production_publication"
    renamed = "mysql57_0024" if mysql else "0026_material_production_names"
    role_names = {
        "AD_PRODUCTION_CREATOR": ("广告制作发布人", "制作需求发布人"),
        "AD_PRODUCTION_COMPLETER": ("广告制作完成人", "制作需求完成人"),
    }
    permission_names = {
        "ops.ad_production.view": ("查看广告制作", "查看制作需求"),
        "ops.ad_production.create": ("新建广告制作", "发布制作需求"),
        "ops.ad_production.edit": ("编辑广告制作", "编辑制作需求"),
    }

    def role_catalog():
        return {role["code"]: role for role in client.get("/api/v1/roles", headers=admin).json()}

    def permission_catalog():
        return {
            permission["code"]: permission
            for permission in client.get("/api/v1/roles/permissions", headers=admin).json()
        }

    command.downgrade(config, previous)
    custom = client.post(
        "/api/v1/roles",
        headers=admin,
        json={"code": "CUSTOM_MATERIAL_ROLE", "name": "广告制作发布人", "data_scope": "SELF"},
    )
    assert custom.status_code == 200, custom.text
    before = role_catalog()
    previous_permissions = permission_catalog()
    publisher_id = before["AD_PRODUCTION_CREATOR"]["id"]
    completer_id = before["AD_PRODUCTION_COMPLETER"]["id"]
    user_id, publisher = user_with_role(
        client,
        engine,
        admin,
        name="material_publisher",
        role_id=publisher_id,
        historical_assignment=True,
    )
    with Session(engine) as session:
        historical_audit = session.scalar(
            select(OperationLog).where(
                OperationLog.entity_type == "ROLE",
                OperationLog.action == "ROLE_CREATE",
                OperationLog.entity_id == custom.json()["id"],
            )
        )
        historical_id, historical_snapshot = historical_audit.id, historical_audit.after_data

    command.upgrade(config, renamed)
    after = role_catalog()
    current_permissions = permission_catalog()
    assert after["CUSTOM_MATERIAL_ROLE"] == custom.json()
    for code, (previous_name, name) in role_names.items():
        assert before[code]["name"] == previous_name
        assert after[code] == {
            **before[code],
            "name": name,
            "revision": before[code]["revision"] + 1,
        }
    for code, (previous_name, name) in permission_names.items():
        assert previous_permissions[code]["name"] == previous_name
        assert current_permissions[code] == {
            **previous_permissions[code],
            "name": name,
            "group": "物料制作",
            "parent_group": "运营协作",
        }

    with Session(engine) as session:
        assert session.get(UserRole, (user_id, publisher_id)) is not None
        assert session.get(OperationLog, historical_id).after_data == historical_snapshot
        audits = list(
            session.scalars(
                select(OperationLog)
                .where(
                    OperationLog.request_id == "migration-material-production-names-v1",
                    OperationLog.entity_id.in_((publisher_id, completer_id)),
                )
                .order_by(OperationLog.id)
            )
        )
        assert len(audits) == 4  # fresh upgrade and replay after restoring the previous revision
        assert {audit.entity_id for audit in audits[-2:]} == {publisher_id, completer_id}
        for audit in audits[-2:]:
            code = audit.before_data["code"]
            assert audit.operator_id is None and audit.action == "ROLE_UPDATE"
            assert audit.before_data["name"] == before[code]["name"]
            assert audit.after_data["name"] == after[code]["name"]
        session.get(Role, completer_id).name = "现场设计执行"
        permission_id = previous_permissions["ops.ad_production.edit"]["id"]
        session.get(Permission, permission_id).name = "现场进度维护"
        session.commit()

    command.downgrade(config, previous)
    restored_roles = role_catalog()
    assert (
        restored_roles["AD_PRODUCTION_CREATOR"]["name"] == before["AD_PRODUCTION_CREATOR"]["name"]
    )
    assert restored_roles["AD_PRODUCTION_COMPLETER"]["name"] == "现场设计执行"
    assert permission_catalog()["ops.ad_production.edit"]["name"] == "现场进度维护"
    command.upgrade(config, renamed)
    assert role_catalog()["AD_PRODUCTION_COMPLETER"] == restored_roles["AD_PRODUCTION_COMPLETER"]
    assert permission_catalog()["ops.ad_production.edit"]["name"] == "现场进度维护"
    command.upgrade(config, "head")
    receiver_id, _ = create_ad_receiver(client, engine, admin)
    response = client.post(PATH, headers=publisher, files=form(publication_fields(receiver_id)))
    assert response.status_code == 201, response.text


def exercise_ad_production_publication(api):
    client, engine, _, admin = api
    with Session(engine) as session:
        publisher_role = session.scalar(
            select(Role.id).where(Role.code == "CUSTOMER_SERVICE_OPERATIONS")
        )
    publisher_id, publisher = user_with_role(
        client, engine, admin, name="publication_user", role_id=publisher_role
    )
    receiver_id, receiver = create_ad_receiver(client, engine, admin)
    _, unassigned = create_ad_receiver(client, engine, admin, name="unassigned_ad_reviewer")
    fields = {
        "title": "节日上新物料",
        "content": "请制作门店海报和展架",
        "receiver_id": receiver_id,
    }
    for invalid_fields in (
        {key: value for key, value in fields.items() if key != "title"},
        {key: value for key, value in fields.items() if key != "receiver_id"},
        {**fields, "title": " \u200b "},
        {**fields, "receiver_id": 0},
        {**fields, "due_at": "2026-12-01T18:30:00"},
    ):
        rejected = client.post(PATH, headers=publisher, files=form(invalid_fields))
        assert rejected.status_code == 422, rejected.text

    start = datetime.now(UTC)
    local_deadline = "2030-11-27T18:30:00+08:00"
    released = client.post(
        PATH,
        headers=publisher,
        files=form(
            {**fields, "due_at": local_deadline, "issuer": "客户端历史名称"},
            ("poster.png", PNG, "image/png"),
        ),
    )
    assert released.status_code == 201, released.text
    row = released.json()
    published_at = datetime.fromisoformat(row["created_at"])
    assert start - timedelta(seconds=1) <= published_at <= datetime.now(UTC)
    assert row["title"] == fields["title"] and row["publisher_display_name"] == "publication_user"
    assert row["created_by"] == publisher_id
    assert datetime.fromisoformat(row["due_at"]) == datetime.fromisoformat(local_deadline)
    assert row["work_date"] == published_at.date().isoformat()
    another = client.post(PATH, headers=publisher, files=form({**fields, "title": "无需截止时间"}))
    assert another.status_code == 201, another.text
    assert another.json()["due_at"] is None and another.json()["issuer"] == "publication_user"
    visible = client.get(
        PATH,
        headers=publisher,
        params={"keyword": "节日上新", "published_from": published_at.isoformat()},
    ).json()
    assert [item["id"] for item in visible["items"]] == [row["id"]]
    exclusive = client.get(
        PATH, headers=publisher, params={"published_before": published_at.isoformat()}
    ).json()
    assert exclusive["total"] == 0
    assert (
        client.get(
            PATH, headers=publisher, params={"published_from": "2030-11-27T08:00:00"}
        ).status_code
        == 422
    )

    detail = f"{PATH}/{row['id']}"
    state = f"{detail}/status"
    assert (
        client.get(detail, headers=receiver).json()["publisher_display_name"] == "publication_user"
    )
    assert (
        client.patch(
            state, headers=publisher, json={"revision": 1, "status": "IN_PROGRESS"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            state, headers=unassigned, json={"revision": 1, "status": "IN_PROGRESS"}
        ).status_code
        == 404
    )
    started = client.patch(state, headers=receiver, json={"revision": 1, "status": "IN_PROGRESS"})
    assert started.status_code == 200, started.text
    assert started.json() == {
        **row,
        "can_delete": False,
        "can_withdraw": False,
        "status": "IN_PROGRESS",
        "revision": 2,
        "updated_at": started.json()["updated_at"],
    }
    done = {"revision": 2, "status": "COMPLETED", "completed_by_id": receiver_id}
    completed = client.patch(state, headers=receiver, json=done)
    assert completed.status_code == 200, completed.text
    assert completed.json()["completed_by_id"] == receiver_id
    assert client.patch(state, headers=receiver, json=done).status_code == 409
    logs = client.get(
        "/api/v1/audits",
        headers=admin,
        params={"entity_type": "AD_PRODUCTION", "entity_id": row["id"]},
    ).json()["items"]
    assert logs[0]["operator"]["id"] == receiver_id
    assert logs[0]["action"] == "STATUS_CHANGE"
    assert logs[0]["after"]["status"] == "COMPLETED"
    assert logs[1]["before"]["status"] == "NOT_STARTED"

    cleared = client.patch(
        detail,
        headers=admin,
        files=form(
            {
                **FIELDS,
                "content": row["content"],
                "status": "COMPLETED",
                "revision": 3,
                "clear_due_at": "true",
            }
        ),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["due_at"] is None and cleared.json()["title"] == fields["title"]
    assert cleared.json()["created_at"] == row["created_at"]


def exercise_ad_production_publication_migration(api):
    client, engine, admin_id, admin = api
    is_mysql = engine.dialect.name == "mysql"
    config_file = "alembic-mysql.ini" if is_mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / config_file))
    prior = "mysql57_0022" if is_mysql else "0024_ad_production_roles"
    command.downgrade(config, prior)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO ops_ad_production "
                "(id, work_date, content, issuer, status, created_at, created_by, "
                "updated_at, revision) "
                "VALUES (77, '2026-10-18', '旧需求原文', '历史下发人', 'IN_PROGRESS', "
                "CURRENT_TIMESTAMP, :admin_id, CURRENT_TIMESTAMP, 1)"
            ),
            {"admin_id": admin_id},
        )
    command.upgrade(config, "head")
    detail = f"{PATH}/77"
    old = client.get(detail, headers=admin).json()
    assert old["title"] is None and old["due_at"] is None
    assert old["work_date"] == "2026-10-18" and old["content"] == "旧需求原文"
    assert old["publisher_display_name"] and old["created_by"] == admin_id
    status = client.patch(
        f"{detail}/status", headers=admin, json={"revision": 1, "status": "SHIPPING"}
    )
    assert status.status_code == 200, status.text
    assert status.json()["title"] is None and status.json()["content"] == old["content"]
    update = client.patch(
        detail,
        headers=admin,
        files=form({**FIELDS, "title": "补充的需求标题", "revision": 2, "status": "SHIPPING"}),
    )
    assert update.status_code == 200, update.text
    with pytest.raises(RuntimeError, match=r"(?:[Dd]owngrade refused|[Rr]efus.*downgrade)"):
        command.downgrade(config, prior)
    # MySQL commits the earlier DDL before reaching the refusal. Check the retained row
    # at that schema, then restore the current head before invoking the current app.
    if is_mysql:
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "mysql57_0023"
            assert (
                db.scalar(text("SELECT title FROM ops_ad_production WHERE id=77"))
                == "补充的需求标题"
            )
    command.upgrade(config, "head")
    restored = client.get(detail, headers=admin)
    assert restored.status_code == 200, restored.text
    assert restored.json()["title"] == "补充的需求标题"
    assert restored.json()["kind"] == "MATERIAL"

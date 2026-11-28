import json
from pathlib import Path

import pytest
from ad_production_acceptance import (
    PATH,
    PNG,
    create_ad_receiver,
    form,
    publication_fields,
    user_with_role,
    user_with_scope,
)
from alembic.config import Config
from feedback_ad_rich_text_acceptance import IMAGE_KEY, RICH, stored_image_id
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.models.entities import Notification, OperationLog, Role, User
from app.models.enums import UserStatus

CC_ENTITIES = {"MATERIAL": "AD_PRODUCTION_MATERIAL_CC", "MERCHANT_AD": "AD_PRODUCTION_MERCHANT_CC"}
OPTIONS = f"{PATH}/cc-options"
CC_TABLE = "ops_ad_production_cc_user"


def _create(client, headers, receiver_id, kind, **fields):
    return client.post(
        PATH,
        headers=headers,
        files=form(publication_fields(receiver_id, kind=kind, **fields)),
    )


def _status(client, headers, item, status, **fields):
    return client.patch(
        f"{PATH}/{item['id']}/status",
        headers=headers,
        json={"status": status, "revision": item["revision"], **fields},
    )


def _edit(client, headers, item, **fields):
    return client.patch(
        f"{PATH}/{item['id']}",
        headers=headers,
        files=form(
            {
                "revision": item["revision"],
                "work_date": item["work_date"],
                "status": item["status"],
                "issuer": item["issuer"],
                "content": item["content"],
                **fields,
            }
        ),
    )


def _record(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def _cc_ids(item):
    return {user["id"] for user in item["cc_users"]}


def _notices(client, headers, item):
    return [
        row
        for row in _record(client.get("/api/v1/notifications", headers=headers))
        if row["entity_id"] == item["id"]
        and row["entity_type"] in {"AD_PRODUCTION", CC_ENTITIES[item["kind"]]}
    ]


def _check_notice(notice, item, *, title=None):
    assert notice["type"] == "SYSTEM"
    assert notice["entity_type"] == CC_ENTITIES[item["kind"]]
    assert item["title"] not in notice["content"]
    if title:
        assert title in notice["title"]


def _set_user_status(engine, user_id, status):
    with Session(engine) as db:
        db.get(User, user_id).status = status
        db.commit()


def exercise_ad_production_cc(api, kind):
    client, engine, publisher_id, admin = api
    receiver_id, receiver = create_ad_receiver(client, engine, admin, name="cc_receiver")
    watcher_id, watcher = user_with_scope(
        client, engine, admin, name="cc_without_permission", permissions=set()
    )
    with Session(engine) as db:
        tester_role = db.scalar(select(Role.id).where(Role.code == "TESTER"))
    deactivated_id, deactivated = user_with_role(
        client, engine, admin, name="cc_deactivated", role_id=tester_role
    )
    prefix = "ops.merchant_ad" if kind == "MERCHANT_AD" else "ops.ad_production"
    editor_id, editor = user_with_scope(
        client,
        engine,
        admin,
        name="cc_self_editor",
        permissions={f"{prefix}.view", f"{prefix}.edit"},
    )
    outsider_id, outsider = user_with_role(
        client, engine, admin, name="cc_unrelated", role_id=tester_role
    )
    _set_user_status(engine, deactivated_id, UserStatus.DISABLED)

    unrelated = _record(_create(client, admin, receiver_id, kind, title="未共享的独立记录"), 201)
    assert unrelated["cc_users"] == []
    assert client.get(OPTIONS, headers=watcher, params={"kind": kind}).status_code == 403
    options = _record(client.get(OPTIONS, headers=admin, params={"kind": kind, "keyword": "CC_"}))
    assert {watcher_id, editor_id, outsider_id, receiver_id} <= {row["id"] for row in options}
    assert deactivated_id not in {row["id"] for row in options}
    assert {"id", "display_name"} == set(options[0])
    for invalid in (
        "[",
        "{}",
        "[true]",
        json.dumps([watcher_id, watcher_id]),
        json.dumps([deactivated_id]),
    ):
        assert _create(client, admin, receiver_id, kind, cc_user_ids=invalid).status_code == 422
    assert _record(client.get(PATH, headers=admin, params={"kind": kind}))["total"] == 1
    assert _notices(client, watcher, unrelated) == []

    _set_user_status(engine, deactivated_id, UserStatus.ACTIVE)
    original = [receiver_id, watcher_id, deactivated_id, publisher_id]
    created = _record(
        client.post(
            PATH,
            headers=admin,
            files=[
                *form(
                    publication_fields(
                        receiver_id,
                        kind=kind,
                        title="抄送验收使用的内部标题",
                        content=RICH,
                        content_format="HTML",
                        cc_user_ids=json.dumps(original),
                    ),
                    ("gallery.png", PNG, "image/png"),
                ),
                ("content_images", (IMAGE_KEY, PNG, "image/png")),
            ],
        ),
        201,
    )
    detail = f"{PATH}/{created['id']}"
    assert _cc_ids(created) == set(original)
    assert {"id": watcher_id, "display_name": "cc_without_permission"} in created["cc_users"]
    assert _record(client.get(detail, headers=watcher)) == {**created, "can_delete": False}
    inline_id = stored_image_id(created["content"])
    gallery_id = created["images"][0]["file_id"]
    image_urls = (f"{detail}/content-images/{inline_id}", f"{detail}/images/{gallery_id}")
    for url in image_urls:
        assert client.get(url, headers=watcher).content == PNG
        assert client.get(url, headers=outsider).status_code == 403
    assert client.get(detail).status_code == 401
    assert client.get(detail, headers=outsider).status_code == 403
    assert client.get(f"{PATH}/{unrelated['id']}", headers=watcher).status_code == 403
    assert client.get(PATH, headers=watcher, params={"kind": kind}).status_code == 403
    assert client.get("/api/v1/users", headers=watcher).status_code == 403
    assert _edit(client, watcher, created, cc_user_ids="[]").status_code == 403
    assert _status(client, watcher, created, "IN_PROGRESS").status_code == 403

    for uid, headers in [
        (receiver_id, receiver),
        (watcher_id, watcher),
        (deactivated_id, deactivated),
        (publisher_id, admin),
    ]:
        (notice,) = _notices(client, headers, created)
        _check_notice(
            notice,
            created,
            title="新的商家广告" if kind == "MERCHANT_AD" and uid == receiver_id else "抄送",
        )
    _set_user_status(engine, deactivated_id, UserStatus.DISABLED)

    unchanged = _record(_edit(client, admin, created, title="仅更新标题"))
    assert _cc_ids(unchanged) == set(original)
    assert len(_notices(client, watcher, created)) == 1
    assert len(_notices(client, receiver, created)) == 1

    updated_ids = [receiver_id, deactivated_id, publisher_id, editor_id]
    next_fields = {"cc_user_ids": json.dumps(updated_ids), "status": "IN_PROGRESS"}
    stale = _edit(client, admin, created, **next_fields)
    assert (
        stale.status_code == 409
        and stale.json()["data"]["current_revision"] == unchanged["revision"]
    )
    assert _notices(client, editor, created) == []
    started = _record(_edit(client, admin, unchanged, **next_fields))
    assert _cc_ids(started) == set(updated_ids)
    assert len(_notices(client, watcher, created)) == 1
    assert client.get(detail, headers=watcher).status_code == 403
    for url in image_urls:
        assert client.get(url, headers=watcher).status_code == 403
    assert _record(client.get(detail, headers=editor)) == {**started, "can_withdraw": False}
    assert _record(client.get(PATH, headers=editor, params={"kind": kind}))["total"] == 0
    assert _edit(client, editor, started, cc_user_ids="[]").status_code == 404
    assert (
        client.get(
            OPTIONS, headers=editor, params={"kind": kind, "ad_id": created["id"]}
        ).status_code
        == 404
    )
    assert len(_notices(client, receiver, created)) == 2
    (notice,) = _notices(client, editor, created)
    _check_notice(notice, started, title="抄送")
    assert ("处理中" if kind == "MERCHANT_AD" else "进行中") in notice["content"]

    identical_status = _record(_status(client, receiver, started, "IN_PROGRESS"))
    assert len(_notices(client, editor, created)) == 1
    completion = {"completed_by_id": receiver_id}
    if kind == "MERCHANT_AD":
        completion["processing_result"] = "内部处理结果"
    assert _status(client, editor, identical_status, "COMPLETED", **completion).status_code == 404
    done = _record(_status(client, receiver, identical_status, "COMPLETED", **completion))
    assert _cc_ids(done) == set(updated_ids)
    assert len(_notices(client, receiver, created)) == 3
    issuer_notices = _notices(client, admin, created)
    assert len(issuer_notices) == 3
    if kind == "MERCHANT_AD":
        (completion_notice,) = (row for row in issuer_notices if "已完成" in row["title"])
        _check_notice(completion_notice, done)
        assert completion["processing_result"] not in completion_notice["content"]
    assert len(_notices(client, editor, created)) == 2
    assert len(_notices(client, watcher, created)) == 1
    assert _notices(client, outsider, created) == []

    emptied = _record(_edit(client, admin, done, cc_user_ids="[]"))
    assert emptied["cc_users"] == []
    assert client.get(detail, headers=editor).status_code == 404
    assert len(_notices(client, editor, created)) == 2
    with Session(engine) as db:
        disabled_notices = list(
            db.scalars(select(Notification).where(Notification.user_id == deactivated_id))
        )
        assert len(disabled_notices) == 1
        assert disabled_notices[0].entity_id == created["id"]
        log = db.scalars(
            select(OperationLog)
            .where(
                OperationLog.entity_type == "AD_PRODUCTION",
                OperationLog.entity_id == created["id"],
                OperationLog.action == "UPDATE",
            )
            .order_by(OperationLog.id.desc())
        ).first()
        assert log is not None
        assert set(log.before_data["cc_user_ids"]) == set(updated_ids)
        assert log.after_data["cc_user_ids"] == []


def exercise_ad_production_cc_migration(api):
    client, engine, publisher_id, admin = api
    receiver_id, _ = create_ad_receiver(client, engine, admin, name="cc_migration_receiver")
    existing = _record(_create(client, admin, receiver_id, "MATERIAL"), 201)
    detail = f"{PATH}/{existing['id']}"
    mysql = engine.dialect.name == "mysql"
    ini = "alembic-mysql.ini" if mysql else "alembic.ini"
    previous = "mysql57_0027" if mysql else "0029_ops_role_defaults"
    head = "mysql57_0029" if mysql else "0031_production_version_deletion"
    config = Config(str(Path(__file__).resolve().parents[1] / ini))

    command.downgrade(config, previous)
    assert not inspect(engine).has_table(CC_TABLE)
    command.upgrade(config, head)
    assert _record(client.get(detail, headers=admin)) == existing
    columns = inspect(engine).get_pk_constraint(CC_TABLE)["constrained_columns"]
    assert columns == ["ad_production_id", "user_id"]
    assert {row["referred_table"] for row in inspect(engine).get_foreign_keys(CC_TABLE)} == {
        "ops_ad_production",
        "sys_user",
    }

    shared = _record(_edit(client, admin, existing, cc_user_ids=json.dumps([publisher_id])))
    with pytest.raises(RuntimeError, match="CC relationships exist"):
        command.downgrade(config, previous)
    # MySQL committed the harmless newer downgrade before the CC guard refused.
    command.upgrade(config, head)
    assert _record(client.get(detail, headers=admin)) == shared
    assert len(_notices(client, admin, shared)) == 1
    with Session(engine) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == head

    cleared = _record(_edit(client, admin, shared, cc_user_ids="[]"))
    command.downgrade(config, previous)
    command.upgrade(config, head)
    assert _record(client.get(detail, headers=admin)) == cleared
    assert len(_notices(client, admin, shared)) == 1

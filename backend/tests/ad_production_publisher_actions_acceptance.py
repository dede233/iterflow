import json

from ad_production_acceptance import (
    PATH,
    PNG,
    create_ad_receiver,
    form,
    publication_fields,
    user_with_scope,
)
from feedback_ad_rich_text_acceptance import IMAGE_KEY, RICH, stored_image_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AdProduction, AttachmentRelation, Notification, OperationLog

NOTIFICATIONS = "/api/v1/notifications"
REASON = "活动已经撤销"


def _json(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def _set_status(client, actor, item, status, **fields):
    return client.patch(
        f"{PATH}/{item['id']}/status",
        headers=actor,
        json={"revision": item["revision"], "status": status, **fields},
    )


def _notices(client, actor, ad_id):
    return [
        item
        for item in _json(client.get(NOTIFICATIONS, headers=actor))
        if item["entity_id"] == ad_id and (item["entity_type"] or "").startswith("AD_PRODUCTION")
    ]


def exercise_ad_production_publisher_actions(api, kind):
    client, engine, _, admin = api
    prefix = "ops.merchant_ad" if kind == "MERCHANT_AD" else "ops.ad_production"
    publisher_id, publisher = user_with_scope(
        client,
        engine,
        admin,
        name="soft_delete_publisher",
        permissions={f"{prefix}.view", f"{prefix}.create", "sys.audit.view"},
    )
    receiver_id, receiver = create_ad_receiver(client, engine, admin, name="soft_delete_receiver")
    copied_id, copied = user_with_scope(
        client, engine, admin, name="soft_delete_copied", permissions=set()
    )
    cc_ids = [copied_id, receiver_id] if kind == "MERCHANT_AD" else [copied_id]

    def create(**fields):
        return client.post(
            PATH,
            headers=publisher,
            files=[
                *form(
                    publication_fields(
                        receiver_id,
                        kind=kind,
                        cc_user_ids=json.dumps(cc_ids),
                        content=RICH,
                        content_format="HTML",
                        **fields,
                    ),
                    ("poster.png", PNG, "image/png"),
                ),
                ("content_images", (IMAGE_KEY, PNG, "image/png")),
            ],
        )

    def delete(item, actor=publisher, **changes):
        return client.request(
            "DELETE",
            f"{PATH}/{item['id']}",
            headers=actor,
            json={"revision": item["revision"], "reason": REASON, **changes},
        )

    def withdraw(item, actor=publisher, **changes):
        return client.post(
            f"{PATH}/{item['id']}/withdraw",
            headers=actor,
            json={"revision": item["revision"], "reason": REASON, **changes},
        )

    assert create(status="WITHDRAWN").status_code == 422
    pending = _json(create(), 201)
    detail = f"{PATH}/{pending['id']}"
    inline_id = stored_image_id(pending["content"])
    gallery_id = pending["images"][0]["file_id"]
    images = (f"{detail}/content-images/{inline_id}", f"{detail}/images/{gallery_id}")
    assert pending["can_delete"] and not pending["can_withdraw"]
    (listed_pending,) = _json(client.get(PATH, headers=publisher, params={"kind": kind}))["items"]
    assert listed_pending == pending, {
        key: (pending[key], listed_pending[key])
        for key in pending
        if pending[key] != listed_pending[key]
    }
    assert not _json(client.get(detail, headers=receiver))["can_delete"]
    assert not _json(client.get(detail, headers=copied))["can_delete"]
    assert all(client.get(url, headers=copied).content == PNG for url in images)
    (copied_notice,) = _notices(client, copied, pending["id"])
    assert _json(client.get(f"{NOTIFICATIONS}/unread-count", headers=copied))["unread_count"] == 1

    for other in (receiver, copied, admin):
        assert delete(pending, other).status_code == 403
    assert delete(pending, {}).status_code == 401
    assert delete(pending, reason=" ").status_code == 422
    assert delete(pending, reason="错误\x00原因").status_code == 422
    assert withdraw(pending).status_code == 409
    assert _set_status(client, receiver, pending, "WITHDRAWN").status_code == 422
    current = _json(_set_status(client, receiver, pending, "NOT_STARTED"))
    stale = _json(delete(pending), 409)
    assert stale["data"]["current_revision"] == current["revision"]
    assert stale["data"]["current_updated_by"] == receiver_id
    deleted = _json(delete(current, reason=f" {REASON} "))
    assert deleted == {"id": current["id"], "revision": current["revision"] + 1, "deleted": True}
    for actor in (publisher, receiver, admin):
        assert client.get(detail, headers=actor).status_code == 404
        assert all(client.get(url, headers=actor).status_code == 404 for url in images)
        assert _json(client.get(PATH, headers=actor, params={"kind": kind}))["total"] == 0
    assert client.get(detail, headers=copied).status_code == 403
    assert all(client.get(url, headers=copied).status_code == 403 for url in images)
    assert client.get(f"/api/v1/files/{gallery_id}/download", headers=admin).status_code == 404
    assert delete(current).status_code == 404
    assert _set_status(client, receiver, current, "IN_PROGRESS").status_code == 404
    assert _notices(client, receiver, pending["id"]) == []
    assert _notices(client, copied, pending["id"]) == []
    assert _json(client.get(f"{NOTIFICATIONS}/unread-count", headers=copied))["unread_count"] == 0
    assert _json(client.post(f"{NOTIFICATIONS}/read-all", headers=copied))["updated_count"] == 0
    assert _json(client.post(f"{NOTIFICATIONS}/{copied_notice['id']}/read", headers=copied))["ok"]

    audit = _json(
        client.get(
            "/api/v1/audits",
            headers=publisher,
            params={
                "entity_type": "AD_PRODUCTION",
                "entity_id": pending["id"],
                "action": "SOFT_DELETE",
            },
        )
    )["items"]
    assert len(audit) == 1 and audit[0]["operator"]["id"] == publisher_id
    assert audit[0]["before"]["status"] == "NOT_STARTED"
    assert audit[0]["after"]["reason"] == REASON
    assert audit[0]["after"]["revision"] == deleted["revision"]
    with Session(engine) as db:
        row = db.get(AdProduction, pending["id"])
        assert row.deleted_by == publisher_id and row.deleted_at is not None
        assert row.delete_reason == REASON and row.revision == deleted["revision"]
        assert db.get(Notification, copied_notice["id"]).read_at is None
        attached = db.scalars(
            select(AttachmentRelation.file_id).where(
                AttachmentRelation.entity_id == pending["id"],
                AttachmentRelation.file_id.in_((gallery_id, inline_id)),
            )
        ).all()
        assert set(attached) == {gallery_id, inline_id}

    pending = _json(create(), 201)
    detail = f"{PATH}/{pending['id']}"
    started = _json(_set_status(client, receiver, pending, "IN_PROGRESS"))
    assert not started["can_withdraw"]
    assert _json(client.get(detail, headers=publisher))["can_withdraw"]
    assert delete(started).status_code == 409
    assert withdraw(started, receiver).status_code == 403
    assert withdraw(started, copied).status_code == 403
    assert withdraw(started, admin).status_code == 403
    stale = _json(withdraw(pending), 409)
    assert stale["data"]["current_revision"] == started["revision"]

    unstarted = _json(_set_status(client, receiver, started, "NOT_STARTED"))
    assert not _json(client.get(detail, headers=publisher))["can_delete"]
    assert delete(unstarted).status_code == 409
    active_status = "SHIPPING" if kind == "MATERIAL" else "IN_PROGRESS"
    in_flight = _json(_set_status(client, receiver, unstarted, active_status))
    withdrawn = _json(withdraw(in_flight))
    assert withdrawn["status"] == "WITHDRAWN" and withdrawn["revision"] == in_flight["revision"] + 1
    assert not withdrawn["can_withdraw"] and not withdrawn["can_delete"]
    assert _json(client.get(detail, headers=copied)) == withdrawn
    gallery_id = withdrawn["images"][0]["file_id"]
    assert client.get(f"{detail}/images/{gallery_id}", headers=copied).content == PNG
    listed = _json(
        client.get(PATH, headers=publisher, params={"kind": kind, "status": "WITHDRAWN"})
    )
    assert listed["items"] == [withdrawn]
    receiver_type = "AD_PRODUCTION_MATERIAL"
    cc_type = "AD_PRODUCTION_MATERIAL_CC"
    if kind == "MERCHANT_AD":
        receiver_type = cc_type = "AD_PRODUCTION_MERCHANT_CC"
    for actor, entity_type in ((receiver, receiver_type), (copied, cc_type)):
        (notice,) = [n for n in _notices(client, actor, withdrawn["id"]) if "撤回" in n["content"]]
        assert notice["entity_type"] == entity_type
        assert REASON not in notice["content"]
    assert _set_status(client, receiver, withdrawn, "IN_PROGRESS").status_code == 409
    assert withdraw(withdrawn).status_code == 409
    assert delete(withdrawn).status_code == 409
    edit_fields = {
        field: withdrawn[field] for field in ("work_date", "issuer", "status", "revision")
    }
    edit = client.patch(
        detail,
        headers=publisher,
        files=form({**edit_fields, "content": "尝试修改已撤回内容"}),
    )
    assert edit.status_code == 409
    with Session(engine) as db:
        (log,) = db.scalars(
            select(OperationLog).where(
                OperationLog.entity_type == "AD_PRODUCTION",
                OperationLog.entity_id == withdrawn["id"],
                OperationLog.action == "WITHDRAW",
            )
        ).all()
        assert log.operator_id == publisher_id and log.created_at is not None
        assert log.before_data["status"] == active_status
        assert log.after_data["status"] == "WITHDRAWN" and log.after_data["reason"] == REASON
        assert db.get(AdProduction, withdrawn["id"]).deleted_at is None

    completed_fields = {"processing_result": "商家已确认"} if kind == "MERCHANT_AD" else {}
    done = _json(
        _set_status(
            client,
            receiver,
            _json(create(), 201),
            "COMPLETED",
            completed_by_id=receiver_id,
            **completed_fields,
        )
    )
    assert withdraw(done).status_code == 409
    assert delete(done).status_code == 409

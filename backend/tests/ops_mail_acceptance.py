import json
from datetime import UTC, datetime, timedelta

from ad_production_acceptance import create_ad_receiver, user_with_scope
from ad_production_cc_acceptance import _create, _edit, _record, _status
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_mail_delivery_postgres import drain

from app.core.config import get_settings
from app.models.entities import CollaborationEvent, MailPreference, NotificationDelivery, User
from app.services.delivery_service import DeliveryService

MONITOR = "/api/v1/admin/mail-delivery-monitor"
MAILBOXES = {
    "publisher": "ops-publisher@example.test",
    "receiver": "ops-receiver@example.test",
    "watcher": "ops-watcher@example.test",
}


def exercise_ops_mail(api, kind, smtp_sink, monkeypatch):
    client, engine, admin_id, admin = api
    receiver_id, receiver = create_ad_receiver(client, engine, admin, name="ops_mail_receiver")
    watcher_id, watcher = user_with_scope(
        client, engine, admin, name="ops_mail_watcher", permissions={"dashboard.view"}
    )
    monkeypatch.setattr(get_settings(), "smtp_allowlist", ",".join(MAILBOXES.values()))
    with Session(engine) as db:
        for uid, role, mode in (
            (admin_id, "publisher", "ALL"),
            (receiver_id, "receiver", "TASKS"),
            (watcher_id, "watcher", "ALL"),
        ):
            addr = MAILBOXES[role]
            db.get(User, uid).email = addr
            db.add(
                MailPreference(
                    user_id=uid,
                    mode=mode,
                    verified_email=addr,
                    verified_at=datetime.now(UTC) - timedelta(minutes=1),
                )
            )
        db.commit()

    def create():
        response = _create(
            client,
            admin,
            receiver_id,
            kind,
            cc_user_ids=json.dumps([receiver_id, watcher_id]),
            content="保密的门店业务内容",
        )
        return _record(response, 201)

    def rows(item, action):
        with Session(engine) as db:
            return list(
                db.scalars(
                    select(NotificationDelivery)
                    .join(CollaborationEvent)
                    .where(
                        CollaborationEvent.entity_id == item["id"],
                        CollaborationEvent.action == action,
                    )
                )
            )

    record = create()
    drain(engine)
    drain(engine)
    assert sorted(str(message["To"]) for message in smtp_sink) == sorted(
        [MAILBOXES["receiver"], MAILBOXES["watcher"]]
    )
    path = "material" if kind == "MATERIAL" else "merchant-ad"
    for message in smtp_sink:
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        expected = f"/#/notifications/{path}/{record['id']}"
        assert expected in plain and expected in html
        assert "保密的门店业务内容" not in plain + html
    assert {(row.user_id, row.channel, row.status) for row in rows(record, "OPS_ASSIGNED")} == {
        (receiver_id, "EMAIL", "SENT")
    }
    assert {(row.user_id, row.channel, row.status) for row in rows(record, "OPS_CC_ADDED")} == {
        (watcher_id, "EMAIL", "SENT")
    }
    assert client.get(f"/api/v1/ad-productions/{record['id']}", headers=watcher).status_code == 200

    record = _record(_status(client, receiver, record, "IN_PROGRESS"))
    drain(engine)
    assert str(smtp_sink[-1]["To"]) == MAILBOXES["watcher"]
    (skip,) = [row for row in rows(record, "OPS_CC_UPDATED") if row.user_id == receiver_id]
    assert (skip.status, skip.last_error) == ("SKIPPED", "EMAIL_NOT_A_TASK")
    monitored = _record(client.get(f"{MONITOR}/{skip.id}", headers=admin))
    assert monitored["error_code"] == skip.last_error
    assert monitored["event_label"] == "抄送的制作需求有更新"

    completion_fields = {"processing_result": "内部处理结果"} if kind == "MERCHANT_AD" else {}
    record = _record(
        _status(
            client, receiver, record, "COMPLETED", completed_by_id=receiver_id, **completion_fields
        )
    )
    drain(engine)
    assert {(row.user_id, row.status) for row in rows(record, "OPS_COMPLETED")} == {
        (admin_id, "SENT")
    }

    pending = create()
    with Session(engine) as db:
        DeliveryService(db).expand()
    pending = _record(_edit(client, admin, pending, cc_user_ids="[]"))
    drain(engine)
    [(copied_user, status, reason)] = [
        (row.user_id, row.status, row.last_error) for row in rows(pending, "OPS_CC_ADDED")
    ]
    assert (copied_user, status, reason) == (watcher_id, "SKIPPED", "ACCESS_REVOKED")
    assert client.get(f"/api/v1/ad-productions/{pending['id']}", headers=watcher).status_code == 403
    assert {(row.user_id, row.status) for row in rows(pending, "OPS_ASSIGNED")} == {
        (receiver_id, "SENT")
    }

    removed = create()
    response = client.request(
        "DELETE",
        f"/api/v1/ad-productions/{removed['id']}",
        headers=admin,
        json={"revision": removed["revision"], "reason": "隔离演练删除"},
    )
    assert response.status_code == 200, response.text
    drain(engine)
    assert {(row.user_id, row.status, row.last_error) for row in rows(removed, "OPS_ASSIGNED")} == {
        (receiver_id, "SKIPPED", "ACCESS_REVOKED")
    }

    # Expand the assignment before the terminal action, then deliver both events.
    # ALL allows the receiver to get a withdrawal email while the stale task is skipped.
    with Session(engine) as db:
        db.get(MailPreference, receiver_id).mode = "ALL"
        db.commit()
    for terminal, expected_action, mailbox in (
        ("COMPLETED", "OPS_COMPLETED", MAILBOXES["publisher"]),
        ("WITHDRAWN", "OPS_WITHDRAWN", MAILBOXES["receiver"]),
    ):
        queued = create()
        with Session(engine) as db:
            DeliveryService(db).expand()
        (assignment,) = rows(queued, "OPS_ASSIGNED")
        assert assignment.status == "PENDING"
        queued = _record(_status(client, receiver, queued, "IN_PROGRESS"))
        if terminal == "COMPLETED":
            queued = _record(
                _status(
                    client,
                    receiver,
                    queued,
                    terminal,
                    completed_by_id=receiver_id,
                    **completion_fields,
                )
            )
        else:
            queued = _record(
                client.post(
                    f"/api/v1/ad-productions/{queued['id']}/withdraw",
                    headers=admin,
                    json={"revision": queued["revision"], "reason": "隔离演练撤回"},
                )
            )
        before = len(smtp_sink)
        drain(engine)
        assert {
            (row.user_id, row.status, row.last_error) for row in rows(queued, "OPS_ASSIGNED")
        } == {(receiver_id, "SKIPPED", "OPS_ASSIGNMENT_NO_LONGER_ACTIONABLE")}
        (terminal_delivery,) = rows(queued, expected_action)
        assert terminal_delivery.status == "SENT"
        new_messages = smtp_sink[before:]
        subject = "制作需求已完成" if terminal == "COMPLETED" else "制作需求已撤回"
        assert [
            str(message["To"]) for message in new_messages if subject in str(message["Subject"])
        ] == [mailbox]
        assert all("有制作需求待处理" not in str(message["Subject"]) for message in new_messages)
        monitored = _record(client.get(f"{MONITOR}/{assignment.id}", headers=admin))
        assert monitored["error_code"] == "OPS_ASSIGNMENT_NO_LONGER_ACTIONABLE"

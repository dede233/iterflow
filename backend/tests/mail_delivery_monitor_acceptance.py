import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest.mock import Mock

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.entities import (
    CollaborationEvent,
    Feedback,
    MailPreference,
    Notification,
    NotificationDelivery,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.models.enums import DataScope, FeedbackType
from app.services.delivery_service import DeliveryService

MONITOR_PATH = "/api/v1/admin/mail-delivery-monitor"
RECIPIENTS_PATH = f"{MONITOR_PATH}/recipients"
LEGACY_PATH = "/api/v1/admin/mail-deliveries"


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def exercise_mail_delivery_monitor(api, monkeypatch):
    client, engine, admin_id, admin = api
    mailbox = "private-monitor-address@example.test"
    smtp_detail = f"Unexpected SMTP reply for {mailbox}"
    monkeypatch.setattr(get_settings(), "smtp_enabled", True)

    with Session(engine) as db:
        recipient = User(
            username="monitor-recipient",
            display_name="监控验收接收人",
            email=mailbox,
            password_hash="unused",
            must_change_password=False,
        )
        lead = User(
            username="monitor-lead",
            display_name="监控验收研发负责人",
            password_hash="unused",
            must_change_password=False,
        )
        no_history = User(
            username="monitor-no-history",
            display_name=" ",
            password_hash="unused",
            must_change_password=False,
        )
        custom_role = Role(
            code="MONITOR_CUSTOM", name="监控验收自定义角色", data_scope=DataScope.ALL
        )
        db.add_all([recipient, lead, no_history, custom_role])
        db.flush()
        recipient_id, recipient_revision = recipient.id, recipient.revision
        lead_id = lead.id
        no_history_id = no_history.id
        db.get(User, admin_id).display_name = recipient.display_name
        lead_role = db.scalars(select(Role).where(Role.code == "DEVELOPMENT_LEAD")).one()
        edit_permission = db.scalars(
            select(Permission).where(Permission.code == "sys.user.edit")
        ).one()
        db.add(UserRole(user_id=lead_id, role_id=lead_role.id))
        db.add(UserRole(user_id=no_history_id, role_id=custom_role.id))
        db.add(RolePermission(role_id=custom_role.id, permission_id=edit_permission.id))
        lead_role_id, edit_permission_id = lead_role.id, edit_permission.id
        db.commit()

    assert client.get(MONITOR_PATH).status_code == 401
    assert client.get(RECIPIENTS_PATH).status_code == 401
    for denied_user_id in (lead_id, recipient_id, no_history_id):
        member = _headers(denied_user_id)
        assert client.get(MONITOR_PATH, headers=member).status_code == 403
        assert client.get(RECIPIENTS_PATH, headers=member).status_code == 403
        assert (
            client.get("/api/v1/auth/me", headers=member).json()["can_view_mail_deliveries"]
            is False
        )
    with Session(engine) as db:
        db.add(RolePermission(role_id=lead_role_id, permission_id=edit_permission_id))
        db.commit()
    lead_headers = _headers(lead_id)
    assert client.get(LEGACY_PATH, headers=lead_headers).status_code == 200
    assert (
        client.get("/api/v1/auth/me", headers=lead_headers).json()["can_view_mail_deliveries"]
        is True
    )
    assert client.get("/api/v1/auth/me", headers=admin).json()["can_view_mail_deliveries"] is True

    invited = client.post(
        f"/api/v1/users/{recipient_id}/email-verification",
        headers=admin,
        json={"revision": recipient_revision},
    )
    assert invited.status_code == 204, invited.text
    own_preferences = client.get("/api/v1/me/mail-preferences", headers=admin).json()
    self_requested = client.post(
        "/api/v1/me/email-verification",
        headers=admin,
        json={"revision": own_preferences["revision"], "email": "self@example.test"},
    )
    assert self_requested.status_code == 200, self_requested.text

    now = datetime.now(UTC).replace(microsecond=0)
    event_time = now - timedelta(minutes=5)
    with Session(engine) as db:
        assert DeliveryService(db).expand() == 2
        invite_delivery, self_delivery = db.scalars(
            select(NotificationDelivery)
            .join(CollaborationEvent)
            .where(CollaborationEvent.action == "VERIFY_EMAIL")
            .order_by(NotificationDelivery.user_id.desc())
        ).all()
        assert invite_delivery.user_id == recipient_id and invite_delivery.channel == "EMAIL"
        assert self_delivery.user_id == admin_id and self_delivery.channel == "EMAIL"
        invite_id, self_id = invite_delivery.id, self_delivery.id
        invite_delivery.status = "RETRY"
        invite_delivery.attempts = 2
        invite_delivery.last_error = smtp_detail
        invite_delivery.created_at = now
        invite_delivery.next_attempt_at = now + timedelta(minutes=3)
        self_delivery.created_at = now - timedelta(minutes=1)
        invite_event = db.get(CollaborationEvent, invite_delivery.event_id)
        invite_event.created_at = event_time

        collaboration_event = CollaborationEvent(
            entity_type="FEEDBACK",
            entity_id=1,
            action="RECIPIENT_ADDED",
            actor_id=admin_id,
            recipient_ids=[recipient_id],
            created_at=event_time,
            processed_at=now,
        )
        db.add(collaboration_event)
        db.flush()
        email = NotificationDelivery(
            event_id=collaboration_event.id,
            user_id=recipient_id,
            channel="EMAIL",
            status="FAILED",
            attempts=1,
            last_error="SMTP_550",
            queued_email=mailbox,
            created_at=now - timedelta(minutes=2),
        )
        db.add(email)
        other_channels = []
        for channel in ("SITE", "WECOM"):
            other_channels.append(
                NotificationDelivery(
                    event_id=collaboration_event.id,
                    user_id=lead_id,
                    channel=channel,
                    status="RETRY",
                    created_at=now + timedelta(minutes=1),
                )
            )
        db.add_all(other_channels)
        db.commit()
        email_id = email.id
        other_ids = [delivery.id for delivery in other_channels]

    first = client.get(MONITOR_PATH, headers=admin, params={"page": 1, "page_size": 2})
    assert first.status_code == 200, first.text
    assert mailbox not in first.text and smtp_detail not in first.text
    page = first.json()
    assert (page["total"], page["page"], page["page_size"]) == (3, 1, 2)
    assert page["can_resend_mail_deliveries"] is True
    assert [item["id"] for item in page["items"]] == [invite_id, self_id]
    invite, own_verification = page["items"]
    assert set(invite) == {
        "id",
        "user_id",
        "username",
        "display_name",
        "kind",
        "status",
        "attempts",
        "error_code",
        "created_at",
        "next_attempt_at",
        "resend_token",
        "resend_block_reason",
    }
    assert (invite["user_id"], invite["username"]) == (recipient_id, "monitor-recipient")
    assert invite["display_name"] == "监控验收接收人"
    assert (invite["kind"], invite["status"], invite["attempts"], invite["error_code"]) == (
        "EMAIL_VERIFICATION",
        "RETRY",
        2,
        "UNKNOWN",
    )
    assert datetime.fromisoformat(invite["created_at"]).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(invite["next_attempt_at"]).utcoffset() == timedelta(0)
    assert own_verification["kind"] == "EMAIL_VERIFICATION"
    assert own_verification["status"] == "PENDING"
    assert own_verification["resend_token"] is None
    assert own_verification["resend_block_reason"] == "邮件已在等待发送"

    second = client.get(MONITOR_PATH, headers=admin, params={"page": 2, "page_size": 2}).json()
    assert second["total"] == 3
    assert [item["id"] for item in second["items"]] == [email_id]
    failed = second["items"][0]
    assert failed["kind"] == "COLLABORATION"
    assert failed["error_code"] == "SMTP_550"
    assert failed["next_attempt_at"] is None
    assert failed["resend_token"] is None

    invite_detail_path = f"{MONITOR_PATH}/{invite_id}"
    collaboration_detail_path = f"{MONITOR_PATH}/{email_id}"
    assert client.get(invite_detail_path).status_code == 401
    for denied_user_id in (recipient_id, no_history_id):
        member = _headers(denied_user_id)
        assert client.get(invite_detail_path, headers=member).status_code == 403
        assert client.get(f"{MONITOR_PATH}/missing", headers=member).status_code == 403
    for unavailable_id in [*other_ids, "missing"]:
        assert client.get(f"{MONITOR_PATH}/{unavailable_id}", headers=admin).status_code == 404

    current_mailbox = "current-address@example.test"
    with Session(engine) as db:
        db.get(User, recipient_id).email = current_mailbox
        db.commit()
    summary_keys = (
        "id",
        "username",
        "display_name",
        "kind",
        "status",
        "attempts",
        "error_code",
        "created_at",
        "next_attempt_at",
    )
    for headers, path, item, label in (
        (admin, invite_detail_path, invite, "验证通知邮箱"),
        (lead_headers, collaboration_detail_path, failed, "有反馈需要处理"),
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "private, no-store"
        assert all(value not in response.text for value in (mailbox, current_mailbox, smtp_detail))
        detail = response.json()
        assert detail == {
            **{key: item[key] for key in summary_keys},
            "masked_email": "p***@example.test",
            "event_label": label,
            "event_created_at": event_time.isoformat().replace("+00:00", "Z"),
        }

    # Imported or old rows may have no usable address. Even a valid current
    # account address is irrelevant when reading that historical delivery.
    for stored_address, masked_address, action, label in (
        (None, None, "private event text", "协作通知"),
        ("private..address@example.test", None, "REQUIREMENT_private event text", "协作通知"),
        ("private@example.test,bcc@example.test", None, "private event text", "协作通知"),
        ("x@example.test", "***@example.test", "private event text", "协作通知"),
        (
            "a***@example.test",
            "***@example.test",
            "REQUIREMENT_STATUS_TESTING",
            "关联需求有新进展 · 需求已提交验收",
        ),
    ):
        with Session(engine) as db:
            stored_delivery = db.get(NotificationDelivery, email_id)
            stored_delivery.queued_email = stored_address
            # An unknown historic action must never be echoed into the label.
            db.get(CollaborationEvent, stored_delivery.event_id).action = action
            db.commit()
        response = client.get(collaboration_detail_path, headers=lead_headers)
        assert response.status_code == 200, response.text
        assert response.json()["masked_email"] == masked_address
        assert response.json()["event_label"] == label

    retry_page = client.get(
        MONITOR_PATH,
        headers=lead_headers,
        params={"status": "RETRY", "kind": "EMAIL_VERIFICATION", "user_id": recipient_id},
    ).json()
    assert retry_page["can_resend_mail_deliveries"] is False
    assert retry_page["total"] == 1
    assert [item["id"] for item in retry_page["items"]] == [invite_id]
    assert retry_page["items"][0]["error_code"] == "UNKNOWN"
    filtered_empty = client.get(
        MONITOR_PATH,
        headers=admin,
        params={"status": "RETRY", "kind": "COLLABORATION", "user_id": recipient_id},
    ).json()
    assert (filtered_empty["items"], filtered_empty["total"]) == ([], 0)
    empty = client.get(MONITOR_PATH, headers=admin, params={"page": 3, "page_size": 2}).json()
    assert (empty["items"], empty["total"]) == ([], 3)
    for bad in (
        {"status": "NOPE"},
        {"kind": "NOPE"},
        {"page_size": 101},
        {"page": 0},
        {"user_id": 0},
    ):
        assert client.get(MONITOR_PATH, headers=admin, params=bad).status_code == 422

    duplicate_search = client.get(
        RECIPIENTS_PATH, headers=lead_headers, params={"keyword": "验收接收人", "page_size": 1}
    ).json()
    assert duplicate_search["total"] == 2
    duplicate_next = client.get(
        RECIPIENTS_PATH,
        headers=lead_headers,
        params={"keyword": "验收接收人", "page_size": 1, "page": 2},
    ).json()
    first_person, second_person = duplicate_search["items"][0], duplicate_next["items"][0]
    assert first_person["display_name"] == second_person["display_name"] == "监控验收接收人"
    assert {first_person["user_id"], second_person["user_id"]} == {recipient_id, admin_id}
    assert first_person["username"] != second_person["username"]
    username_match = client.get(
        RECIPIENTS_PATH, headers=lead_headers, params={"keyword": "MONITOR-RECIPIENT"}
    ).json()
    assert username_match["items"] == [
        {"user_id": recipient_id, "username": "monitor-recipient", "display_name": "监控验收接收人"}
    ]
    literal_match = client.get(
        RECIPIENTS_PATH, headers=lead_headers, params={"keyword": "%"}
    ).json()
    assert literal_match["total"] == 0
    assert client.get(RECIPIENTS_PATH, headers=lead_headers).json()["total"] == 2
    selected = {"selected_id": no_history_id}
    assert client.get(RECIPIENTS_PATH, headers=lead_headers, params=selected).json()["total"] == 0
    fallback = client.get(RECIPIENTS_PATH, headers=admin, params=selected).json()
    assert fallback["items"] == [
        {
            "user_id": no_history_id,
            "username": "monitor-no-history",
            "display_name": "monitor-no-history",
        }
    ]
    no_history_page = client.get(
        MONITOR_PATH, headers=admin, params={"user_id": no_history_id}
    ).json()
    assert (no_history_page["items"], no_history_page["total"]) == ([], 0)

    with Session(engine) as db:
        audit = db.scalars(
            select(OperationLog).where(OperationLog.action == "DELIVERY_MONITOR_VIEW")
        ).all()
        assert sorted(row.operator_id for row in audit) == sorted([admin_id] * 5 + [lead_id])
        detail_audit = db.scalars(
            select(OperationLog)
            .where(OperationLog.action == "DELIVERY_DETAIL_VIEW")
            .order_by(OperationLog.id)
        ).all()
        assert [(row.operator_id, row.after_data) for row in detail_audit] == [
            (admin_id, {"delivery_id": invite_id}),
            *((lead_id, {"delivery_id": email_id}) for _ in range(6)),
        ]
        view_permission = db.scalars(
            select(Permission).where(Permission.code == "sys.user.view")
        ).one()
        db.add(RolePermission(role_id=lead_role_id, permission_id=view_permission.id))
        db.get(Role, lead_role_id).data_scope = DataScope.ALL
        db.commit()
    assert client.get(RECIPIENTS_PATH, headers=lead_headers, params=selected).json()["total"] == 1

    with Session(engine) as db:
        db.get(Role, lead_role_id).enabled = False
        super_role = db.scalars(select(Role).where(Role.code == "SUPER_ADMIN")).one()
        super_role.enabled = False
        db.commit()
    assert client.get(MONITOR_PATH, headers=lead_headers).status_code == 403
    assert client.get(RECIPIENTS_PATH, headers=lead_headers).status_code == 403
    assert client.get(collaboration_detail_path, headers=lead_headers).status_code == 403
    assert client.get(MONITOR_PATH, headers=admin).status_code == 403
    assert client.get(invite_detail_path, headers=admin).status_code == 403
    assert client.get("/api/v1/auth/me", headers=admin).json()["can_view_mail_deliveries"] is False

    with Session(engine) as db:
        super_role = db.scalars(select(Role).where(Role.code == "SUPER_ADMIN")).one()
        super_role.enabled = True
        super_role.is_system = False
        db.commit()
    assert client.get(MONITOR_PATH, headers=admin).status_code == 403


def exercise_mail_delivery_resend(api, monkeypatch):
    client, engine, admin_id, admin = api
    mailbox = "resend-monitor@example.test"
    smtp = Mock()
    monkeypatch.setattr("app.services.delivery_service.send_smtp", smtp)
    monkeypatch.setattr(get_settings(), "smtp_enabled", True)
    monkeypatch.setattr(get_settings(), "smtp_allowlist", mailbox)

    now = datetime.now(UTC) + timedelta(seconds=10)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr("app.services.delivery_service.datetime", FixedClock)

    with Session(engine) as db:
        lead = User(
            username="resend-lead",
            display_name="邮件重发研发负责人",
            password_hash="unused",
            must_change_password=False,
        )
        db.add(lead)
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "DEVELOPMENT_LEAD"))
        permission = db.scalar(select(Permission).where(Permission.code == "sys.user.edit"))
        db.add(UserRole(user_id=lead.id, role_id=role.id))
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        lead_headers = _headers(lead.id)
        db.commit()

    preferences = client.get("/api/v1/me/mail-preferences", headers=admin).json()
    created = client.post(
        "/api/v1/me/email-verification",
        headers=admin,
        json={"revision": preferences["revision"], "email": mailbox},
    )
    assert created.status_code == 200, created.text
    with Session(engine) as db:
        sender = DeliveryService(db)
        assert sender.expand() == 1
        assert sender.deliver_one()
        row = db.scalar(select(NotificationDelivery))
        delivery_id, event_id, original_lease = row.id, row.event_id, row.next_attempt_at
        challenge_expires_at = db.get(MailPreference, admin_id).challenge_expires_at
    assert smtp.call_count == 1
    original_message = smtp.call_args.args[0]
    path = f"{MONITOR_PATH}/{delivery_id}/resend"

    def item(headers=admin):
        response = client.get(MONITOR_PATH, headers=headers, params={"user_id": admin_id})
        assert response.status_code == 200, response.text
        return response.json()["items"][0]

    def enqueue(token, headers=admin):
        return client.post(path, headers=headers, json={"resend_token": token})

    initial = item()
    token = initial["resend_token"]
    assert initial["status"] == "SENT" and token and initial["resend_block_reason"] is None
    assert mailbox not in str(initial)
    assert item(lead_headers)["resend_token"] is None
    assert enqueue(token, lead_headers).status_code == 403
    assert enqueue(token, {}).status_code == 401
    assert enqueue("0" * 64).status_code == 409
    assert enqueue("invalid").status_code == 422
    assert (
        client.post(
            f"{MONITOR_PATH}/missing/resend", headers=admin, json={"resend_token": token}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{LEGACY_PATH}/{delivery_id}/retry", headers=lead_headers, json={"attempts": 1}
        ).status_code
        == 409
    )

    barrier = Barrier(2)

    def request_resend():
        barrier.wait(timeout=5)
        return enqueue(token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(request_resend) for _ in range(2)]
        assert sorted(result.result(timeout=15).status_code for result in results) == [204, 409]

    assert smtp.call_count == 1
    waiting = item()
    assert waiting["status"] == "PENDING" and waiting["resend_token"] is None
    with Session(engine) as db:
        row = db.get(NotificationDelivery, delivery_id)
        assert (row.event_id, row.attempts, row.last_error) == (event_id, 0, None)
        assert db.get(MailPreference, admin_id).challenge_expires_at == challenge_expires_at
        audit = db.scalar(select(OperationLog).where(OperationLog.action == "DELIVERY_RESEND"))
        assert audit.operator_id == admin_id
        assert audit.before_data == {"status": "SENT", "attempts": 1, "error_code": None}
        assert audit.after_data == {
            "delivery_id": delivery_id,
            "user_id": admin_id,
            "status": "PENDING",
        }
        assert DeliveryService(db).deliver_one()
        db.refresh(row)
        assert (row.status, row.attempts, row.next_attempt_at) == ("SENT", 1, original_lease)
    assert smtp.call_count == 2
    resent_message = smtp.call_args.args[0]
    assert original_message["Message-ID"] != resent_message["Message-ID"]
    assert original_message.get_body(preferencelist=("plain",)).get_content() == (
        resent_message.get_body(preferencelist=("plain",)).get_content()
    )
    new_token = item()["resend_token"]
    assert new_token and new_token != token
    assert enqueue(token).status_code == 409

    with Session(engine) as db:
        challenge = db.get(MailPreference, admin_id)
        challenge.challenge_expires_at = now - timedelta(minutes=1)
        db.commit()
    expired = item()
    assert expired["resend_token"] is None and "验证码已失效" in expired["resend_block_reason"]
    assert enqueue(new_token).status_code == 409
    with Session(engine) as db:
        challenge = db.get(MailPreference, admin_id)
        challenge.challenge_expires_at = challenge_expires_at
        db.commit()

    assert enqueue(new_token).status_code == 204
    with Session(engine) as db:
        db.get(MailPreference, admin_id).challenge_expires_at = now - timedelta(minutes=1)
        db.commit()
        assert DeliveryService(db).deliver_one()
        row = db.get(NotificationDelivery, delivery_id)
        assert (row.status, row.last_error) == ("SKIPPED", "PREFERENCE_OR_EMAIL_CHANGED")
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert db.scalar(select(func.count()).select_from(CollaborationEvent)) == 1
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(
                    OperationLog.action == "DELIVERY_RESEND",
                )
            )
            == 2
        )
    assert smtp.call_count == 2
    assert item()["resend_token"] is None
    assert enqueue(new_token).status_code == 409


def exercise_failed_collaboration_mail_resend(api, monkeypatch):
    client, engine, admin_id, admin = api
    mailbox = "collaboration-resend@example.test"
    smtp = Mock(side_effect=smtplib.SMTPResponseException(550, b"private smtp reply"))
    monkeypatch.setattr("app.services.delivery_service.send_smtp", smtp)
    monkeypatch.setattr(get_settings(), "smtp_enabled", True)
    monkeypatch.setattr(get_settings(), "smtp_allowlist", mailbox)

    with Session(engine) as db:
        db.get(User, admin_id).email = mailbox
        db.add(
            MailPreference(
                user_id=admin_id,
                mode="ALL",
                verified_email=mailbox,
                verified_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        feedback = Feedback(
            feedback_no="MAIL-RESEND",
            title="邮件重发测试反馈",
            description="验证协作邮件的重发门禁",
            feedback_type=FeedbackType.OTHER,
            submitter_id=admin_id,
            created_by=admin_id,
        )
        db.add(feedback)
        db.flush()
        db.add(
            CollaborationEvent(
                entity_type="FEEDBACK",
                entity_id=feedback.id,
                action="RECIPIENT_ADDED",
                actor_id=admin_id,
                recipient_ids=[admin_id],
            )
        )
        db.commit()
        sender = DeliveryService(db)
        assert sender.expand() == 1
        assert sender.deliver_one() and sender.deliver_one()
        site_id = db.scalar(
            select(NotificationDelivery.id).where(NotificationDelivery.channel == "SITE")
        )

    def read_delivery():
        return client.get(MONITOR_PATH, headers=admin).json()["items"][0]

    failed = read_delivery()
    assert failed["kind"] == "COLLABORATION"
    assert failed["status"] == "FAILED" and failed["error_code"] == "SMTP_550"
    token = failed["resend_token"]
    assert token and failed["resend_block_reason"] is None
    path = f"{MONITOR_PATH}/{failed['id']}/resend"
    payload = {"resend_token": token}
    assert (
        client.post(f"{MONITOR_PATH}/{site_id}/resend", headers=admin, json=payload).status_code
        == 404
    )
    assert smtp.call_count == 1

    with Session(engine) as db:
        db.get(MailPreference, admin_id).mode = "OFF"
        db.commit()
    assert read_delivery()["resend_token"] is None
    assert client.post(path, headers=admin, json=payload).status_code == 409
    with Session(engine) as db:
        db.get(MailPreference, admin_id).mode = "ALL"
        db.commit()

    assert client.post(path, headers=admin, json=payload).status_code == 204
    smtp.side_effect = [smtplib.SMTPResponseException(451, b"temporary failure"), None]
    with Session(engine) as db:
        sender = DeliveryService(db)
        assert sender.deliver_one()
        row = db.get(NotificationDelivery, failed["id"])
        assert (row.status, row.attempts, row.last_error) == ("RETRY", 1, "SMTP_451")
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert sender.deliver_one()
        db.refresh(row)
        assert (row.status, row.attempts, row.last_error) == ("SENT", 2, None)
        assert db.scalar(select(func.count()).select_from(CollaborationEvent)) == 1
        assert db.scalar(select(func.count()).select_from(Notification)) == 1
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 2
        audit = db.scalar(select(OperationLog).where(OperationLog.action == "DELIVERY_RESEND"))
        assert audit.before_data == {"status": "FAILED", "attempts": 1, "error_code": "SMTP_550"}
    original_id, resend_id, retry_id = [call.args[0]["Message-ID"] for call in smtp.call_args_list]
    assert original_id != resend_id == retry_id

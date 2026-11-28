from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

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
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from alembic import command
from app.models.entities import (
    AdProduction,
    NotificationDelivery,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    UserRole,
)

MERCHANT = "MERCHANT_AD"
MATERIAL = "MATERIAL"
RESULT = "已和门店确认处理方案\n<文字原样保留>"
MATERIAL_PERMISSIONS = {f"ops.ad_production.{action}" for action in ("view", "create", "edit")}
MERCHANT_PERMISSIONS = {f"ops.merchant_ad.{action}" for action in ("view", "create", "edit")}
AUDIT_VIEW = "sys.audit.view"


def _issue(client, headers, receiver_id, **fields):
    reply = client.post(
        PATH, headers=headers, files=form(publication_fields(receiver_id, **fields))
    )
    assert reply.status_code == 201, reply.text
    return reply.json()


def _status(client, headers, task, status, **fields):
    return client.patch(
        f"{PATH}/{task['id']}/status",
        headers=headers,
        json={"revision": task["revision"], "status": status, **fields},
    )


def _notices(client, headers, task_id):
    reply = client.get("/api/v1/notifications", headers=headers)
    assert reply.status_code == 200, reply.text
    return [
        item
        for item in reply.json()
        if item["entity_type"] == "AD_PRODUCTION" and item["entity_id"] == task_id
    ]


def exercise_ad_production_default_roles(api):
    client, engine, _, admin = api
    with Session(engine) as session:
        roles = dict(session.execute(select(Role.code, Role.id)).all())
    _, operations = user_with_role(
        client,
        engine,
        admin,
        name="ops_default_publisher",
        role_id=roles["CUSTOMER_SERVICE_OPERATIONS"],
    )
    receiver_id, designer = create_ad_receiver(client, engine, admin, name="ops_default_designer")
    other_id, other = create_ad_receiver(client, engine, admin, name="ops_other_designer")
    for kind in (MATERIAL, MERCHANT):
        record = _issue(client, operations, receiver_id, kind=kind, title="运营发布")
        assert _status(client, operations, record, "IN_PROGRESS").status_code == 403
        assert _status(client, other, record, "IN_PROGRESS").status_code == 404
        started = _status(client, designer, record, "IN_PROGRESS")
        assert started.status_code == 200, started.text
        fields = {"completed_by_id": receiver_id}
        if kind == MERCHANT:
            fields["processing_result"] = RESULT
        completed = _status(client, designer, started.json(), "COMPLETED", **fields)
        assert completed.status_code == 200, completed.text
        assert completed.json()["completed_by_id"] == receiver_id

        design_record = _issue(client, designer, other_id, kind=kind, title="设计发布")
        assert design_record["created_by"] == receiver_id
        assert client.get(f"{PATH}/{design_record['id']}", headers=operations).status_code == 200


def exercise_ad_production_creator_correction(api):
    client, engine, _, admin = api
    with Session(engine) as session:
        operations_role = session.scalar(
            select(Role.id).where(Role.code == "CUSTOMER_SERVICE_OPERATIONS")
        )
    creator_id, creator = user_with_role(
        client, engine, admin, name="correction_owner", role_id=operations_role
    )
    peer_id, peer = user_with_role(
        client, engine, admin, name="correction_peer", role_id=operations_role
    )
    _, scoped_peer = user_with_scope(
        client,
        engine,
        admin,
        name="correction_scoped_peer",
        permissions={
            code
            for code in MATERIAL_PERMISSIONS | MERCHANT_PERMISSIONS
            if not code.endswith(".edit")
        },
    )
    first_id, first = create_ad_receiver(client, engine, admin, name="correction_first_designer")
    next_id, designer = create_ad_receiver(client, engine, admin, name="correction_next_designer")

    def correct(record, headers=creator, *, images=(), inline=(), removals=(), **changes):
        fields = {
            key: record[key]
            for key in ("work_date", "issuer", "status", "content_format", "content", "revision")
        }
        return client.patch(
            f"{PATH}/{record['id']}",
            headers=headers,
            files=[*form({**fields, **changes}, *images, removals=removals), *inline],
        )

    def options(record, headers):
        return client.get(f"{PATH}/cc-options", headers=headers, params={"ad_id": record["id"]})

    def notices(record, headers):
        reply = client.get("/api/v1/notifications", headers=headers)
        assert reply.status_code == 200, reply.text
        return [
            item
            for item in reply.json()
            if item["entity_id"] == record["id"] and item["entity_type"].startswith("AD_PRODUCTION")
        ]

    for kind in (MATERIAL, MERCHANT):
        submitted = client.post(
            PATH,
            headers=creator,
            files=form(
                publication_fields(first_id, kind=kind), ("incorrect.png", PNG, "image/png")
            ),
        )
        assert submitted.status_code == 201, submitted.text
        record = submitted.json()
        detail = f"{PATH}/{record['id']}"
        assert client.get(detail, headers=peer).status_code == 200
        assert correct(record, peer, title="他人试图修改").status_code == 403
        assert correct(record, scoped_peer, title="范围外修改").status_code == 404
        assert peer_id in {item["id"] for item in options(record, creator).json()}
        assert options(record, peer).status_code == 403
        assert options(record, scoped_peer).status_code == 404
        assert _status(client, creator, record, "IN_PROGRESS").status_code == 403
        for changes in (
            {"work_date": "2026-11-10"},
            {"issuer": "冒用发布人"},
            {"status": "IN_PROGRESS"},
            {"completed_by_id": next_id},
            {"processing_result": RESULT},
        ):
            assert correct(record, title="不应落库", **changes).status_code == 403
        for invalid_receiver in (0, creator_id):
            invalid = correct(record, receiver_id=invalid_receiver)
            assert invalid.status_code == 422, invalid.text
            assert invalid.json()["data"]["field"] == "receiver_id"
        assert client.get(detail, headers=creator).json() == record

        old_file = record["images"][0]["file_id"]
        corrected = correct(
            record,
            title="更正设计标题",
            content=RICH,
            content_format="HTML",
            due_at="2026-12-10T13:30:00+08:00",
            receiver_id=next_id,
            cc_user_ids=f"[{next_id}, {peer_id}]",
            images=(("replacement.png", PNG, "image/png"),),
            inline=(("content_images", (IMAGE_KEY, PNG, "image/png")),),
            removals=(old_file,),
        )
        assert corrected.status_code == 200, corrected.text
        updated = corrected.json()
        assert updated["revision"] == record["revision"] + 1
        assert updated["title"] == "更正设计标题" and updated["receiver_id"] == next_id
        assert updated["due_at"].startswith("2026-12-10T05:30:00")
        assert {item["id"] for item in updated["cc_users"]} == {next_id, peer_id}
        for field in (
            "created_at",
            "created_by",
            "issuer",
            "kind",
            "work_date",
            "status",
            "processing_result",
            "completed_by_id",
        ):
            assert updated[field] == record[field]
        assert client.get(detail, headers=first).status_code == 404
        assert client.get(detail, headers=designer).json() == {**updated, "can_delete": False}
        assert client.get(f"{detail}/images/{old_file}", headers=creator).status_code == 404
        replacement_file = updated["images"][0]["file_id"]
        assert updated["images"][0]["original_name"] == "replacement.png"
        assert client.get(f"{detail}/images/{replacement_file}", headers=creator).content == PNG
        inline_file = stored_image_id(updated["content"])
        assert client.get(f"{detail}/content-images/{inline_file}", headers=creator).content == PNG
        expected_notices = int(kind == MERCHANT)
        assert len(_notices(client, first, record["id"])) == expected_notices
        assignment = notices(record, designer)
        assert len(assignment) == 1
        assert assignment[0]["title"].startswith("新的商家广告" if kind == MERCHANT else "你被抄送")
        assert len(notices(record, peer)) == 1
        assert options(record, peer).status_code == 403

        stale = correct(record, receiver_id=next_id, cc_user_ids="[]")
        assert stale.status_code == 409, stale.text
        assert stale.json()["data"]["current_revision"] == updated["revision"]
        assert stale.json()["data"]["current_updated_by"] == creator_id
        assert client.get(detail, headers=creator).json() == updated
        started = _status(client, designer, updated, "IN_PROGRESS")
        assert started.status_code == 200, started.text
        active = started.json()
        assert correct(active, receiver_id=first_id).status_code == 403
        assert correct(active, receiver_id=0).status_code == 403
        assert options(active, creator).status_code == 200
        continued = correct(active, title="处理中的补充更正", clear_due_at=True, cc_user_ids="[]")
        assert continued.status_code == 200, continued.text
        active = continued.json()
        assert active["status"] == "IN_PROGRESS" and active["due_at"] is None
        assert active["receiver_id"] == next_id
        assert active["cc_users"] == []
        if kind == MATERIAL:
            shipment = _status(client, designer, active, "SHIPPING")
            assert shipment.status_code == 200, shipment.text
            mailed = correct(shipment.json(), title="邮寄中的补充更正")
            assert mailed.status_code == 200 and mailed.json()["status"] == "SHIPPING"
            active = mailed.json()

        receipt = {"completed_by_id": next_id}
        if kind == MERCHANT:
            receipt["processing_result"] = RESULT
        completed = _status(client, designer, active, "COMPLETED", **receipt)
        assert completed.status_code == 200, completed.text
        finished = completed.json()
        stale = correct(active, title="完成期间试图修改")
        assert stale.status_code == 409, stale.text
        assert stale.json()["data"]["current_revision"] == finished["revision"]
        assert (
            correct(finished, title="完成后试图修改", cc_user_ids=f"[{peer_id}]").status_code == 403
        )
        assert options(finished, creator).status_code == 403
        assert client.get(detail, headers=creator).json() == finished
        assert len(notices(record, designer)) == 2
        assert len(notices(record, peer)) == 2
        assert len(_notices(client, creator, record["id"])) == expected_notices

        with Session(engine) as session:
            audits = session.scalars(
                select(OperationLog)
                .where(
                    OperationLog.entity_type == "AD_PRODUCTION",
                    OperationLog.entity_id == record["id"],
                    OperationLog.action == "UPDATE",
                )
                .order_by(OperationLog.id)
            ).all()
        assert [audit.operator_id for audit in audits] == [creator_id] * (
            3 if kind == MATERIAL else 2
        )
        assert audits[0].before_data["receiver_id"] == first_id
        assert audits[0].after_data["receiver_id"] == next_id
        assert audits[0].before_data["image_ids"] == [old_file]
        assert audits[0].after_data["image_ids"] == [replacement_file]
        assert audits[0].before_data["cc_user_ids"] == []
        assert audits[0].after_data["cc_user_ids"] == sorted([next_id, peer_id])
        assert audits[1].after_data["cc_user_ids"] == []

    historical = _issue(client, creator, first_id, status="IN_PROGRESS")
    with Session(engine) as session:
        row = session.get(AdProduction, historical["id"])
        row.receiver_id = None
        row.completed_by_id = first_id
        row.issuer = "  历史发布人  "
        row.content = "旧纯文本\r\n保留原始换行"
        session.commit()
    historical = client.get(f"{PATH}/{historical['id']}", headers=creator).json()
    assert correct(historical, receiver_id=0).status_code == 403
    amended = correct(historical, title="更正历史标题")
    assert amended.status_code == 200, amended.text
    for field in (
        "receiver_id",
        "completed_by_id",
        "issuer",
        "content",
        "content_format",
        "status",
    ):
        assert amended.json()[field] == historical[field]


def exercise_ad_production_kinds(api):
    client, engine, _, admin = api
    with Session(engine) as session:
        creator_role = session.scalar(
            select(Role.id).where(Role.code == "CUSTOMER_SERVICE_OPERATIONS")
        )
    issuer_id, issuer = user_with_role(
        client, engine, admin, name="design_merchant_publisher", role_id=creator_role
    )
    receiver_id, receiver = create_ad_receiver(
        client, engine, admin, name="design_merchant_receiver"
    )
    _, other = create_ad_receiver(client, engine, admin, name="design_unrelated_receiver")

    assert client.get("/api/v1/merchant-ads", headers=admin).status_code == 404
    options = client.get(f"{PATH}/designer-options", headers=issuer).json()
    assert {"id": receiver_id, "display_name": "design_merchant_receiver"} in options
    fields = publication_fields(receiver_id, kind=MERCHANT)
    for status in ("IN_PROGRESS", "SHIPPING", "COMPLETED"):
        reply = client.post(PATH, headers=issuer, files=form({**fields, "status": status}))
        assert reply.status_code == 422
    assert (
        client.post(
            PATH, headers=issuer, files=form({**fields, "receiver_id": issuer_id})
        ).status_code
        == 422
    )

    material = _issue(client, issuer, receiver_id, title="同工作流物料制作")
    task = _issue(client, issuer, receiver_id, kind=MERCHANT, title="同工作流商家广告")
    assert task["id"] != material["id"]
    assert material["kind"] == MATERIAL and material["processing_result"] is None
    assert task["kind"] == MERCHANT and task["status"] == "NOT_STARTED"
    assert task["created_by"] == issuer_id and task["receiver_id"] == receiver_id
    assert task["issuer"] == task["publisher_display_name"] == "design_merchant_publisher"
    assert task["revision"] == 1 and task["processing_result"] is None

    receiver_view = {**task, "can_delete": False}
    assert client.get(PATH, headers=issuer).json()["items"] == [material]
    assert client.get(PATH, headers=receiver, params={"kind": MERCHANT}).json()["items"] == [
        receiver_view
    ]
    assert client.get(PATH, headers=other, params={"kind": MERCHANT}).json()["total"] == 0
    assert client.get(PATH, headers=issuer, params={"kind": "OTHER"}).status_code == 422
    detail = f"{PATH}/{task['id']}"
    assert client.get(detail, headers=other).status_code == 404
    assert client.get(detail, headers=receiver).json() == receiver_view
    assert _status(client, other, task, "IN_PROGRESS").status_code == 404
    assert _status(client, issuer, task, "IN_PROGRESS").status_code == 403
    assert _status(client, receiver, task, "SHIPPING").status_code == 422
    assert _status(client, receiver, task, "IN_PROGRESS", kind=MATERIAL).status_code == 422
    assert (
        _status(client, receiver, task, "IN_PROGRESS", processing_result=RESULT).status_code == 422
    )
    assert _status(client, receiver, task, "COMPLETED", processing_result=RESULT).status_code == 422
    assert (
        _status(client, receiver, task, "COMPLETED", completed_by_id=receiver_id).status_code == 422
    )
    for invalid in (" \u200b\u0301", "文字\x00", "字" * 4001):
        assert (
            _status(
                client,
                receiver,
                task,
                "COMPLETED",
                completed_by_id=receiver_id,
                processing_result=invalid,
            ).status_code
            == 422
        )
    assert _notices(client, issuer, task["id"]) == []
    assert _notices(client, receiver, material["id"]) == []
    assert len(_notices(client, receiver, task["id"])) == 1
    assert _notices(client, other, task["id"]) == []

    started = _status(client, receiver, task, "IN_PROGRESS")
    assert started.status_code == 200, started.text
    assert started.json()["revision"] == 2 and started.json()["processing_result"] is None
    stale = _status(
        client, receiver, task, "COMPLETED", completed_by_id=receiver_id, processing_result=RESULT
    )
    assert stale.status_code == 409 and stale.json()["code"] == 40910
    assert stale.json()["data"]["current_revision"] == 2
    assert stale.json()["data"]["current_updated_by"] == receiver_id

    edit = {
        **publication_fields(receiver_id),
        "status": "COMPLETED",
        "revision": 2,
        "completed_by_id": receiver_id,
    }
    assert (
        client.patch(detail, headers=receiver, files=form({**edit, "kind": MATERIAL})).status_code
        == 422
    )
    assert client.patch(detail, headers=receiver, files=form(edit)).status_code == 422
    completed = client.patch(
        detail, headers=receiver, files=form({**edit, "processing_result": RESULT})
    )
    assert completed.status_code == 200, completed.text
    receipt = completed.json()
    assert receipt["processing_result"] == RESULT and receipt["completed_by_id"] == receiver_id
    assert receipt["status"] == "COMPLETED" and receipt["revision"] == 3
    assert receipt["created_by"] == issuer_id
    assert receipt["publisher_display_name"] == task["publisher_display_name"]
    assert receipt["issuer"] == task["issuer"]
    assert client.get(detail, headers=issuer).json() == receipt
    assert (
        _status(client, receiver, receipt, "COMPLETED", processing_result=None).status_code == 422
    )
    retained = _status(client, receiver, receipt, "COMPLETED")
    assert retained.status_code == 200 and retained.json()["processing_result"] == RESULT
    updated = _status(
        client, receiver, retained.json(), "COMPLETED", processing_result="补充处理结果"
    )
    assert updated.status_code == 200 and updated.json()["processing_result"] == "补充处理结果"
    notices = _notices(client, issuer, task["id"])
    assert len(notices) == 1 and notices[0]["type"] == "SYSTEM"
    assert "门店" not in notices[0]["content"] and "补充处理结果" not in notices[0]["content"]
    reopened = _status(client, receiver, updated.json(), "IN_PROGRESS")
    assert reopened.status_code == 200 and reopened.json()["processing_result"] is None
    assert reopened.json()["completed_by_id"] is None

    shipping = _status(client, receiver, material, "SHIPPING")
    assert shipping.status_code == 200 and shipping.json()["kind"] == MATERIAL
    assert (
        _status(
            client,
            receiver,
            shipping.json(),
            "COMPLETED",
            completed_by_id=receiver_id,
            processing_result=RESULT,
        ).status_code
        == 422
    )
    with Session(engine) as session:
        audits = list(
            session.scalars(
                select(OperationLog)
                .where(
                    OperationLog.entity_type == "AD_PRODUCTION",
                    OperationLog.entity_id == task["id"],
                )
                .order_by(OperationLog.id)
            )
        )
        assert [audit.operator_id for audit in audits] == [issuer_id, *([receiver_id] * 5)]
        assert audits[0].after_data["kind"] == MERCHANT
        assert audits[2].after_data["processing_result"] == RESULT
        assert session.scalar(select(func.count()).select_from(NotificationDelivery)) == 0


def exercise_ad_production_kinds_concurrency(api):
    client, _, _, admin = api
    receiver_id, receiver = create_ad_receiver(client, api[1], admin)
    task = _issue(client, admin, receiver_id, kind=MERCHANT)
    ready = Barrier(2)

    def complete(result):
        ready.wait(timeout=10)
        return _status(
            client,
            receiver,
            task,
            "COMPLETED",
            completed_by_id=receiver_id,
            processing_result=result,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.map(complete, ("第一份结果", "第二份结果"))
    assert sorted((first.status_code, second.status_code)) == [200, 409]
    failed = first if first.status_code == 409 else second
    assert failed.json()["code"] == 40910
    assert len(_notices(client, admin, task["id"])) == 1
    assert len(_notices(client, receiver, task["id"])) == 1


def exercise_ad_production_kind_permissions(api):
    client, engine, _, admin = api
    catalog = client.get("/api/v1/roles/permissions", headers=admin).json()

    def role_with_permissions(name, permissions, scope="ALL"):
        reply = client.post(
            "/api/v1/roles",
            headers=admin,
            json={
                "code": name.upper(),
                "name": name,
                "data_scope": scope,
                "permission_ids": [item["id"] for item in catalog if item["code"] in permissions],
            },
        )
        assert reply.status_code == 200, reply.text
        return reply.json()["id"]

    def actor(name, permissions, scope="ALL"):
        return user_with_role(
            client,
            engine,
            admin,
            name=name,
            role_id=role_with_permissions(name, permissions, scope),
        )

    _, material_creator = actor("ops_material_creator", MATERIAL_PERMISSIONS | {AUDIT_VIEW})
    _, merchant_creator = actor("ops_merchant_creator", MERCHANT_PERMISSIONS | {AUDIT_VIEW})
    _, merchant_viewer = actor(
        "ops_merchant_viewer", {"ops.merchant_ad.view", "ops.ad_production.edit", AUDIT_VIEW}
    )
    _, merchant_creator_without_view = actor("ops_merchant_no_view", {"ops.merchant_ad.create"})
    _, merchant_outsider = actor(
        "ops_merchant_self", MERCHANT_PERMISSIONS | {AUDIT_VIEW}, scope="SELF"
    )
    with Session(engine) as session:
        roles = dict(session.execute(select(Role.code, Role.id)).all())
        permission_ids = dict(session.execute(select(Permission.code, Permission.id)).all())
        for role_code, permission_code in (
            ("DESIGNER", "ops.merchant_ad.edit"),
            ("AD_PRODUCTION_COMPLETER", "ops.ad_production.view"),
            ("AD_PRODUCTION_COMPLETER", "ops.ad_production.edit"),
        ):
            session.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == roles[role_code],
                    RolePermission.permission_id == permission_ids[permission_code],
                )
            )
        session.commit()
    material_receiver_id, material_receiver = user_with_role(
        client, engine, admin, name="ops_material_designer", role_id=roles["DESIGNER"]
    )
    merchant_receiver_id, merchant_receiver = create_ad_receiver(
        client, engine, admin, name="ops_merchant_designer", historical_assignment=True
    )
    options = f"{PATH}/designer-options"
    assert client.get(options, headers=material_creator).json() == [
        {"id": material_receiver_id, "display_name": "ops_material_designer"}
    ]
    assert client.get(options, headers=merchant_creator, params={"kind": MERCHANT}).json() == [
        {"id": merchant_receiver_id, "display_name": "ops_merchant_designer"}
    ]
    assert client.get(options, headers=merchant_creator).status_code == 403
    assert (
        client.get(options, headers=material_creator, params={"kind": MERCHANT}).status_code == 403
    )
    invalid = client.get(options, headers=merchant_creator, params={"kind": "UNKNOWN"})
    assert invalid.status_code == 422 and invalid.json()["code"] == 42290

    for headers, receiver_id, kind, response in (
        (material_creator, merchant_receiver_id, MERCHANT, 403),
        (merchant_creator, material_receiver_id, MATERIAL, 403),
        (merchant_creator_without_view, merchant_receiver_id, MERCHANT, 403),
        (merchant_viewer, merchant_receiver_id, MERCHANT, 403),
        (material_creator, merchant_receiver_id, MATERIAL, 422),
        (merchant_creator, material_receiver_id, MERCHANT, 422),
    ):
        reply = client.post(
            PATH, headers=headers, files=form(publication_fields(receiver_id, kind=kind))
        )
        assert reply.status_code == response, reply.text
        if response == 422:
            assert reply.json()["data"]["field"] == "receiver_id"

    def issue(headers, receiver_id, kind):
        fields = publication_fields(receiver_id, kind=kind, content=RICH, content_format="HTML")
        reply = client.post(
            PATH,
            headers=headers,
            files=[
                *form(fields, ("poster.png", PNG, "image/png")),
                ("content_images", (IMAGE_KEY, PNG, "image/png")),
            ],
        )
        assert reply.status_code == 201, reply.text
        return reply.json()

    material = issue(material_creator, material_receiver_id, MATERIAL)
    merchant = issue(merchant_creator, merchant_receiver_id, MERCHANT)
    assert client.get(PATH, headers=material_creator).json()["items"] == [material]
    assert client.get(PATH, headers=merchant_creator, params={"kind": MERCHANT}).json()[
        "items"
    ] == [merchant]
    assert client.get(PATH, headers=merchant_creator).status_code == 403
    assert client.get(PATH, headers=material_creator, params={"kind": MERCHANT}).status_code == 403
    assert (
        client.get(PATH, headers=merchant_outsider, params={"kind": MERCHANT}).json()["total"] == 0
    )

    for record, allowed, denied in (
        (material, material_receiver, merchant_creator),
        (merchant, merchant_receiver, material_creator),
    ):
        detail = f"{PATH}/{record['id']}"
        for target in (
            detail,
            f"{detail}/images/{record['images'][0]['file_id']}",
            f"{detail}/content-images/{stored_image_id(record['content'])}",
        ):
            assert client.get(target, headers=allowed).status_code == 200
            assert client.get(target, headers=denied).status_code == 404
        edit = form(
            {**publication_fields(record["receiver_id"]), "revision": 1, "status": "IN_PROGRESS"}
        )
        assert client.patch(detail, headers=denied, files=edit).status_code == 404
        assert _status(client, denied, record, "IN_PROGRESS").status_code == 404
        assert client.get(detail, headers=allowed).json()["revision"] == 1

    merchant_detail = f"{PATH}/{merchant['id']}"
    assert client.get(merchant_detail, headers=merchant_viewer).json() == {
        **merchant,
        "can_delete": False,
    }
    assert _status(client, merchant_viewer, merchant, "IN_PROGRESS").status_code == 403
    assert (
        client.patch(
            merchant_detail,
            headers=merchant_viewer,
            files=form(publication_fields(merchant_receiver_id, revision=2, status="IN_PROGRESS")),
        ).status_code
        == 403
    )
    assert _status(client, merchant_outsider, merchant, "IN_PROGRESS").status_code == 404
    wrong_completer = _status(
        client,
        merchant_receiver,
        merchant,
        "COMPLETED",
        completed_by_id=material_receiver_id,
        processing_result=RESULT,
    )
    assert wrong_completer.status_code == 422
    assert wrong_completer.json()["data"]["field"] == "completed_by_id"

    audit_url = "/api/v1/audits"
    first_page = {"size": 1, "entity_type": "AD_PRODUCTION"}
    material_audit = client.get(audit_url, headers=material_creator, params=first_page).json()
    merchant_audit = client.get(audit_url, headers=merchant_creator, params=first_page).json()
    assert material_audit["total"] == merchant_audit["total"] == 1
    assert material_audit["items"][0]["entity_id"] == material["id"]
    assert merchant_audit["items"][0]["entity_id"] == merchant["id"]
    assert (
        client.get(audit_url, headers=material_creator, params={"size": 1}).json() == material_audit
    )
    params = {"entity_type": "AD_PRODUCTION", "entity_id": merchant["id"]}
    assert client.get(audit_url, headers=material_creator, params=params).json()["total"] == 0
    assert client.get(audit_url, headers=merchant_outsider, params=params).json()["total"] == 0
    assert client.get(audit_url, headers=admin, params=first_page).json()["total"] == 2
    for visible, hidden, audit in (
        (material_creator, merchant_creator, material_audit),
        (merchant_creator, material_creator, merchant_audit),
    ):
        audit_path = f"{audit_url}/{audit['items'][0]['id']}"
        assert client.get(audit_path, headers=visible).status_code == 200
        assert client.get(audit_path, headers=hidden).status_code == 404

    started = _status(client, merchant_receiver, merchant, "IN_PROGRESS")
    assert started.status_code == 200 and started.json()["revision"] == 2
    assert _status(client, merchant_receiver, merchant, "IN_PROGRESS").status_code == 409

    delegated_role = role_with_permissions("ops_designer_merchant_edit", {"ops.merchant_ad.edit"})
    with Session(engine) as session:
        session.add(UserRole(user_id=material_receiver_id, role_id=delegated_role))
        session.commit()
    merchant_options = client.get(options, headers=merchant_creator, params={"kind": MERCHANT})
    assert [item["id"] for item in merchant_options.json()] == [
        material_receiver_id,
        merchant_receiver_id,
    ]
    reassignment = client.patch(
        merchant_detail,
        headers=merchant_creator,
        files=form(publication_fields(material_receiver_id, revision=2, status="IN_PROGRESS")),
    )
    assert reassignment.status_code == 200 and reassignment.json()["revision"] == 3
    assert client.get(merchant_detail, headers=material_receiver).status_code == 200
    with Session(engine) as session:
        session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == roles["DESIGNER"],
                RolePermission.permission_id == permission_ids["ops.merchant_ad.view"],
            )
        )
        session.commit()
    assert client.get(merchant_detail, headers=material_receiver).status_code == 404
    assert _status(client, material_receiver, reassignment.json(), "IN_PROGRESS").status_code == 404
    assert client.get(merchant_detail, headers=merchant_creator).json()["receiver_id"] == (
        material_receiver_id
    )


def exercise_ad_production_kinds_migration(api):
    client, engine, admin_id, admin = api
    mysql = engine.dialect.name == "mysql"
    config_file = "alembic-mysql.ini" if mysql else "alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[1] / config_file))
    prior = "mysql57_0024" if mysql else "0026_material_production_names"
    command.downgrade(config, prior)
    assert "kind" not in {col["name"] for col in inspect(engine).get_columns("ops_ad_production")}
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO ops_ad_production "
                "(id, work_date, content, issuer, status, created_by, "
                "created_at, updated_at, revision) "
                "VALUES (107, '2026-11-26', '历史记录', '旧发布人', 'SHIPPING', :uid, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 4)"
            ),
            {"uid": admin_id},
        )
    command.upgrade(config, "head")
    assert not inspect(engine).has_table("ops_merchant_ad")
    material = client.get(f"{PATH}/107", headers=admin).json()
    assert material["kind"] == MATERIAL and material["processing_result"] is None
    assert material["status"] == "SHIPPING" and material["revision"] == 4
    assert material["content"] == "历史记录" and material["issuer"] == "旧发布人"
    command.downgrade(config, prior)
    command.upgrade(config, "head")
    assert client.get(f"{PATH}/107", headers=admin).json() == material

    receiver_id, _ = create_ad_receiver(client, engine, admin)
    task = _issue(client, admin, receiver_id, kind=MERCHANT)
    for statement in (
        "kind = 'UNSUPPORTED'",
        "status = 'SHIPPING'",
        "status = 'COMPLETED', completed_by_id = receiver_id",
        "status = 'COMPLETED', processing_result = 'a'",
    ):
        with engine.begin() as db:
            with pytest.raises(DBAPIError):
                db.execute(
                    text(f"UPDATE ops_ad_production SET {statement} WHERE id = :id"),
                    {"id": task["id"]},
                )
            db.rollback()
    with pytest.raises(RuntimeError, match="downgrade refused"):
        command.downgrade(config, prior)
    if mysql:
        # MySQL has already committed the newer downgrades. Check the retained
        # merchant row before restoring the schema required by the current API.
        with engine.connect() as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "mysql57_0026"
            assert db.execute(
                text("SELECT kind, status, revision FROM ops_ad_production WHERE id = :id"),
                {"id": task["id"]},
            ).one() == (task["kind"], task["status"], task["revision"])
        command.upgrade(config, "head")
    assert client.get(f"{PATH}/{task['id']}", headers=admin).json() == task

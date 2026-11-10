from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import (
    BusinessSystem,
    Feedback,
    OperationLog,
    Permission,
    Requirement,
    Role,
    RolePermission,
    User,
    UserRole,
    Version,
)
from app.models.enums import DataScope


def exercise_entity_activity(fixture):
    client, engine, admin_id, _admin = fixture
    with Session(engine) as db:
        role = Role(code="ACTIVITY_READER", name="详情查看", data_scope=DataScope.SELF)
        reader = User(
            username="activity-reader",
            display_name="最近操作人",
            password_hash="unused",
            must_change_password=False,
        )
        denied = User(
            username="activity-denied",
            display_name="无权用户",
            password_hash="unused",
            must_change_password=False,
        )
        system = BusinessSystem(code="ACTIVITY", name="操作记录验收系统")
        db.add_all([role, reader, denied, system])
        db.flush()
        for kind in ("feedback", "requirement", "version"):
            permission = db.scalar(select(Permission).where(Permission.code == f"rd.{kind}.view"))
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.add(UserRole(user_id=reader.id, role_id=role.id))
        db.flush()
        uid, blocked_id = reader.id, denied.id
        entities = {}
        for kind, model in [
            ("feedback", Feedback),
            ("requirement", Requirement),
            ("version", Version),
        ]:
            common = dict(system_id=system.id, created_by=uid)
            if kind == "feedback":
                item = model(
                    feedback_no="FB-ACT",
                    title="详情反馈",
                    description="合成记录",
                    feedback_type="OTHER",
                    submitter_id=uid,
                    **common,
                )
                foreign = model(
                    feedback_no="FB-FOREIGN",
                    title="不可见反馈",
                    description="其他对象",
                    feedback_type="OTHER",
                    submitter_id=admin_id,
                    created_by=admin_id,
                )
            elif kind == "requirement":
                item = model(
                    requirement_no="REQ-ACT",
                    title="详情需求",
                    description="合成记录",
                    requirement_type="FEATURE",
                    source="DIRECT",
                    **common,
                )
                foreign = model(
                    requirement_no="REQ-FOREIGN",
                    title="不可见需求",
                    description="其他对象",
                    requirement_type="FEATURE",
                    source="DIRECT",
                    created_by=admin_id,
                )
            else:
                item = model(version_no="V-ACT", name="详情版本", owner_id=uid, **common)
                foreign = model(version_no="V-FOREIGN", name="不可见版本", created_by=admin_id)
            db.add_all([item, foreign])
            db.flush()
            records = []
            for index in range(12):
                record = OperationLog(
                    entity_type=kind.upper(),
                    entity_id=item.id,
                    action="UPDATE",
                    operator_id=uid if index < 11 else None,
                    created_at=datetime(2026, 11, 6, tzinfo=UTC),
                    before_data={"password": "never-expose"},
                    after_data={"description": "private-audit-only"},
                    ip_address="127.0.0.9",
                    user_agent="private-agent",
                )
                db.add(record)
                db.flush()
                records.append(record.id)
            db.add(
                OperationLog(
                    entity_type=kind.upper(),
                    entity_id=foreign.id,
                    action="HIDDEN",
                    operator_id=admin_id,
                )
            )
            entities[kind] = (item.id, foreign.id, records, model)
        db.commit()
    reader_headers = {"Authorization": "Bearer " + create_access_token(uid)}
    denied_headers = {"Authorization": "Bearer " + create_access_token(blocked_id)}
    for kind, (ident, foreign_id, records, model) in entities.items():
        path = f"/api/v1/{kind}s/{ident}/activities"
        assert client.get(path).status_code == 401
        assert client.get(path, headers=denied_headers).status_code == 403
        assert (
            client.get(
                f"/api/v1/{kind}s/{foreign_id}/activities", headers=reader_headers
            ).status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/{kind}s/999999/activities", headers=reader_headers).status_code
            == 404
        )
        response = client.get(path, headers=reader_headers)
        assert response.status_code == 200, response.text
        rows = response.json()
        assert len(rows) == 10 and [r["id"] for r in rows] == list(reversed(records))[:10]
        assert rows[0]["operator"] is None
        assert rows[1]["operator"] == {
            "id": uid,
            "username": "activity-reader",
            "display_name": "最近操作人",
        }
        assert set(rows[1]) == {"id", "action", "operator", "created_at"}
        assert "never-expose" not in response.text and "private-agent" not in response.text
        assert client.get("/api/v1/audits", headers=reader_headers).status_code == 403
        with Session(engine) as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(OperationLog)
                    .where(
                        OperationLog.entity_type == kind.upper(), OperationLog.entity_id == ident
                    )
                )
                == 12
            )
        # Current object scope is checked again, even if older audit rows exist.
        if kind != "version":
            with Session(engine) as db:
                db.get(model, ident).deleted_at = datetime.now(UTC)
                db.commit()
            assert client.get(path, headers=reader_headers).status_code == 404
    # Empty history remains empty instead of inventing a last operator.
    with Session(engine) as db:
        empty = Version(version_no="V-EMPTY", name="无记录版本", created_by=uid)
        db.add(empty)
        db.commit()
        empty_id = empty.id
    assert (
        client.get(f"/api/v1/versions/{empty_id}/activities", headers=reader_headers).json() == []
    )

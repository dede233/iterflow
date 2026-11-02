"""Mail notice persistence and old-data compatibility on disposable SQL databases."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.security import create_access_token
from app.models.entities import CollaborationEvent, MailPreference, OperationLog, User

PATH = "/api/v1/me/mail-notice/acknowledge"
PREFERENCES = "/api/v1/me/mail-preferences"


def exercise_notice(fixture, scenario):
    client, engine, admin_id, admin = fixture
    with Session(engine) as db:
        member = User(
            username="notice-member",
            display_name="普通成员",
            password_hash="unused",
            must_change_password=False,
        )
        db.add(member)
        db.commit()
        uid = member.id
    # No business permission or role is needed for one's own preferences.
    headers = {"Authorization": f"Bearer {create_access_token(uid)}"}
    before = client.get(PREFERENCES, headers=headers).json()
    assert before["notice_acknowledged"] is False
    if scenario == "migration":
        mysql = engine.dialect.name == "mysql"
        config = Config(
            str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
        )
        previous = "mysql57_0010" if mysql else "0012_multiple_acceptance"
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE sys_mail_preference SET mode='ALL', verified_email='old@example.test', "
                    "pending_email='pending@example.test', revision=7 WHERE user_id=:uid"
                ),
                {"uid": uid},
            )
        command.downgrade(config, previous)
        with engine.connect() as db:
            old = (
                db.execute(text("SELECT * FROM sys_mail_preference ORDER BY user_id"))
                .mappings()
                .all()
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as db:
            upgraded = (
                db.execute(text("SELECT * FROM sys_mail_preference ORDER BY user_id"))
                .mappings()
                .all()
            )
        assert [
            {k: v for k, v in row.items() if k != "notice_acknowledged_at"} for row in upgraded
        ] == old
        assert all(row["notice_acknowledged_at"] is None for row in upgraded)
        if mysql:
            from app.core.mysql_preflight import validate_mysql

            with engine.connect() as db:
                validate_mysql(db)
        result = client.post(PATH, headers=headers, json={"revision": 7})
        assert result.status_code == 200, result.text
        # Dropping acknowledgements would make users see the notice again: refuse data loss.
        with pytest.raises(RuntimeError, match="refuse lossy downgrade"):
            command.downgrade(config, previous)
        assert client.get(PREFERENCES, headers=headers).json()["notice_acknowledged"]
        return

    assert client.post(PATH, json={"revision": before["revision"]}).status_code == 401
    assert client.post(PATH, headers=headers, json={"revision": 0}).status_code == 422
    with Session(engine) as db:
        event_count = db.scalar(select(func.count()).select_from(CollaborationEvent))
    barrier = Barrier(2)

    def acknowledge():
        barrier.wait()
        return client.post(PATH, headers=headers, json={"revision": before["revision"]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: acknowledge(), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    after = client.get(PREFERENCES, headers=headers).json()
    assert after == {**before, "notice_acknowledged": True, "revision": before["revision"] + 1}
    # A fresh token models another device; acknowledgement remains on the account.
    other_device = {"Authorization": f"Bearer {create_access_token(uid)}"}
    assert client.get(PREFERENCES, headers=other_device).json() == after
    repeated = client.post(PATH, headers=headers, json={"revision": after["revision"]})
    assert repeated.status_code == 200 and repeated.json() == after
    assert client.get(PREFERENCES, headers=admin).json()["notice_acknowledged"] is False
    changed = client.put(
        PREFERENCES, headers=headers, json={"revision": after["revision"], "mode": "OFF"}
    )
    assert changed.status_code == 200 and changed.json()["notice_acknowledged"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(CollaborationEvent)) == event_count
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(
                    OperationLog.action == "MAIL_NOTICE_ACKNOWLEDGED",
                    OperationLog.operator_id == uid,
                )
            )
            == 1
        )
        assert db.get(MailPreference, uid).notice_acknowledged_at is not None
        assert db.get(MailPreference, admin_id).notice_acknowledged_at is None

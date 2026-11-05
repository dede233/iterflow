import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.entities import AnnouncementRead, OperationLog, User

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9eQAAAAASUVORK5CYII="


def exercise_announcements(fixture, scenario):
    client, engine, _uid, admin = fixture
    with Session(engine) as db:
        reader = User(
            username="announcement-reader",
            display_name="公告读者",
            password_hash="unused",
            must_change_password=False,
        )
        db.add(reader)
        db.commit()
        reader_id = reader.id
    user = {"Authorization": "Bearer " + create_access_token(reader_id)}
    payload = {
        "title": "本次更新公告",
        "version_label": "2026.11",
        "release_date": str(date.today()),
        "content": "<h2>新增功能</h2><p>支持更新公告<script>alert(1)</script></p>",
        "important": True,
    }
    assert client.get("/api/v1/announcements").status_code == 401
    assert client.post("/api/v1/announcements", headers=user, json=payload).status_code == 403
    assert client.get("/api/v1/announcements?manage=true", headers=user).status_code == 403
    assert (
        client.post(
            "/api/v1/announcements", headers=admin, json={**payload, "title": "\u200b\u200b"}
        ).status_code
        == 422
    )
    draft = client.post("/api/v1/announcements", headers=admin, json=payload)
    assert draft.status_code == 200, draft.text
    draft = draft.json()
    ident = draft["id"]
    path = f"/api/v1/announcements/{ident}"
    assert "script" not in draft["content"] and draft["published_at"] is None
    assert client.get(path, headers=user).status_code == 404
    assert client.get("/api/v1/announcements", headers=user).json()["total"] == 0
    assert client.post(path + "/read", headers=admin, json={"revision": 1}).status_code == 404
    if scenario == "lifecycle":
        key = "local-11111111-1111-1111-1111-111111111111"
        patched = client.patch(
            path,
            headers=admin,
            json={
                **payload,
                "revision": 1,
                "content": f'<p>截图说明</p><img data-file-id="{key}">',
                "image_uploads": {key: "data:image/png;base64," + PNG},
            },
        )
        assert patched.status_code == 200, patched.text
        draft = patched.json()
        assert draft["revision"] == 2
        import re

        fid = int(re.search(r'data-file-id="(\d+)"', draft["content"])[1])
        image = path + f"/images/{fid}"
        assert client.get(f"/api/v1/files/{fid}/download", headers=admin).status_code == 404
        assert client.get(image, headers=user).status_code == 404
        assert client.get(image, headers=admin).content == base64.b64decode(PNG)
        assert client.patch(path, headers=admin, json={**payload, "revision": 1}).status_code == 409
    published = client.post(path + "/publish", headers=admin, json={"revision": draft["revision"]})
    assert published.status_code == 200, published.text
    published = published.json()
    audit = client.get("/api/v1/audits?entity_type=ANNOUNCEMENT", headers=admin)
    assert audit.status_code == 200, audit.text
    assert any(row["action"] == "PUBLISH" for row in audit.json()["items"])
    rev = published["revision"]
    assert (
        client.post(
            path + "/publish", headers=admin, json={"revision": draft["revision"]}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/announcements/notice", headers=user).json()["unread_count"] == 1
    assert client.patch(path, headers=user, json={**payload, "revision": rev}).status_code == 403
    if scenario == "race":
        barrier = Barrier(2)

        def read():
            barrier.wait(timeout=10)
            return client.post(path + "/read", headers=user, json={"revision": rev})

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: read(), range(2)))
        assert [r.status_code for r in results] == [200, 200]
    else:
        assert client.get(image, headers=user).content == base64.b64decode(PNG)
        another = client.post("/api/v1/announcements", headers=admin, json=payload).json()
        assert (
            client.get(
                f"/api/v1/announcements/{another['id']}/images/{fid}", headers=admin
            ).status_code
            == 404
        )
        assert client.post(path + "/read", headers=user, json={"revision": rev}).status_code == 200
    assert client.get("/api/v1/announcements/notice", headers=user).json()["unread_count"] == 0
    # Different session, same account. Other accounts remain unread.
    second = {"Authorization": "Bearer " + create_access_token(reader_id)}
    assert client.get(path, headers=second).json()["read_at"]
    assert client.get("/api/v1/announcements/notice", headers=admin).json()["unread_count"] == 1
    corrected = client.patch(
        path, headers=admin, json={**payload, "title": "修正后的公告", "revision": rev}
    )
    assert corrected.status_code == 200, corrected.text
    assert client.get("/api/v1/announcements/notice", headers=user).json()["unread_count"] == 0
    assert client.post(path + "/read", headers=second, json={"revision": rev}).status_code == 200
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AnnouncementRead)
                .where(
                    AnnouncementRead.announcement_id == ident, AnnouncementRead.user_id == reader_id
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(OperationLog)
                .where(
                    OperationLog.entity_type == "ANNOUNCEMENT",
                    OperationLog.entity_id == ident,
                    OperationLog.action == "PUBLISH",
                )
            )
            == 1
        )
        if engine.dialect.name == "mysql":
            from app.core.mysql_preflight import validate_mysql

            with engine.connect() as conn:
                validate_mysql(conn)
        assert db.scalar(text("SELECT COUNT(*) FROM rd_release")) == 0


def exercise_announcement_migration(fixture):
    from pathlib import Path

    import pytest
    from alembic.config import Config

    from alembic import command

    client, engine, _uid, admin = fixture
    mysql = engine.dialect.name == "mysql"
    config = Config(
        str(Path(__file__).parents[1] / ("alembic-mysql.ini" if mysql else "alembic.ini"))
    )
    old = "mysql57_0013" if mysql else "0015_system_binding"
    with engine.connect() as db:
        before = db.execute(text("SELECT id, username, revision FROM sys_user ORDER BY id")).all()
    command.downgrade(config, old)
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert (
            db.execute(text("SELECT id, username, revision FROM sys_user ORDER BY id")).all()
            == before
        )
        assert db.scalar(text("SELECT COUNT(*) FROM sys_announcement")) == 0
    result = client.post(
        "/api/v1/announcements",
        headers=admin,
        json={
            "title": "不可丢失的草稿",
            "version_label": "test",
            "release_date": "2026-11-05",
            "content": "<p>必须保留公告内容</p>",
        },
    )
    assert result.status_code == 200, result.text
    with pytest.raises(RuntimeError, match="refuse lossy downgrade"):
        command.downgrade(config, old)
    with engine.connect() as db:
        assert db.scalar(text("SELECT COUNT(*) FROM sys_announcement")) == 1

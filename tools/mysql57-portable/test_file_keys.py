"""Minimal real-5.7 proof, before changing the application migration path."""

import runpy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[2]
DDL = runpy.run_path(str(ROOT / "backend/alembic/mysql_file_keys.py"))
BASELINE = runpy.run_path(str(ROOT / "backend/alembic/mysql_versions/mysql57_0001.py"))[
    "DDL"
]


@pytest.fixture
def proof():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    url = make_url(values["DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == 57357
    admin = create_engine(url.set(port=57358), isolation_level="AUTOCOMMIT")
    name = "iterflow_mysql57_keys_" + uuid4().hex
    with admin.connect() as c:
        assert c.scalar(text("SELECT VERSION()")) == "5.7.44-log"
        assert c.execute(
            text("SELECT @@GLOBAL.innodb_large_prefix, @@GLOBAL.innodb_strict_mode")
        ).one() == (0, 0)
        c.execute(
            text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        )
    engine = create_engine(
        url.set(port=57358, database=name), isolation_level="REPEATABLE READ"
    )
    try:
        with engine.begin() as c:
            c.execute(text("SET SESSION innodb_strict_mode=ON"))
            c.execute(
                text("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
            )
            DDL["create_registry"](c)
            for sql in BASELINE:
                if sql.startswith("CREATE TABLE sys_file"):
                    c.execute(text(DDL["portable_file_ddl"](sql)))
                elif sql.startswith("CREATE TRIGGER `domain_sys_file_"):
                    c.execute(text(sql))
            for sql in DDL["FILE_TRIGGERS"]:
                c.execute(text(sql))
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()


def insert(c, key):
    return c.execute(
        text(
            "INSERT INTO sys_file(storage_key,original_name,mime_type,size,sha256,storage_driver,"
            "created_at,updated_at,revision) VALUES (:key,'proof','text/plain',1,REPEAT('a',64),"
            "'LOCAL',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6),1)"
        ),
        {"key": key.encode("utf-8")},
    ).lastrowid


def test_full_bytes_and_rollback(proof):
    keys = [
        "",
        "Exact",
        "exact",
        "Exact ",
        "😀" * 499 + "甲",
        "😀" * 499 + "乙",
        "a" * 499 + "x",
        "a" * 499 + "y",
        "😀" * 128,
        "😀" * 128 + "a",
    ]
    with proof.begin() as c:
        ids = [insert(c, key) for key in keys]
        assert c.scalar(text("SELECT COUNT(*) FROM sys_file")) == len(keys)
    with proof.connect() as c:
        before = c.scalar(text("SELECT COUNT(*) FROM iterflow_file_key_node"))
        c.rollback()
        insert(c, "😀" * 498 + "新键")
        c.rollback()
        assert c.scalar(text("SELECT COUNT(*) FROM iterflow_file_key_node")) == before
        for key in keys:
            with pytest.raises(DBAPIError) as err:
                insert(c, key)
            assert err.value.orig.args[0] == 1062
            c.rollback()
        with pytest.raises(DBAPIError) as err:
            c.execute(
                text("UPDATE sys_file SET storage_key=:key WHERE id=:id"),
                {"key": keys[4].encode(), "id": ids[5]},
            )
        assert err.value.orig.args[0] == 1062
        c.rollback()
        for sql in [
            "UPDATE iterflow_file_key_node SET segment=X'61' WHERE id=1",
            "DELETE FROM iterflow_file_key_node WHERE id=1",
            "UPDATE sys_file SET storage_key_leaf_id=1 WHERE id=" + str(ids[4]),
        ]:
            with pytest.raises(DBAPIError) as err:
                c.execute(text(sql))
            assert err.value.orig.args[0] == 1644
            c.rollback()


def test_old_snapshot_and_concurrent_duplicates(proof):
    key = "😀" * 499 + "竞"
    with proof.connect() as old:
        old.scalar(text("SELECT COUNT(*) FROM sys_file"))
        with proof.begin() as writer:
            insert(writer, key)
        with pytest.raises(DBAPIError) as err:
            insert(old, key)
        assert err.value.orig.args[0] == 1062
        old.rollback()
    barrier = Barrier(2)

    def worker(_):
        with proof.connect() as c:
            barrier.wait(timeout=10)
            try:
                insert(c, "😀" * 499 + "并")
                c.commit()
                return 200
            except DBAPIError as err:
                c.rollback()
                assert err.orig.args[0] in {1062, 1213}
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, range(2))) == [200, 409]
    with proof.connect() as c:
        assert c.scalar(text("SELECT COUNT(*) FROM sys_file")) == 2


def test_overlong_key_cannot_be_silently_truncated(proof):
    # Raw SQL uses the instance's empty SQL mode, rather than the app connect hook.
    with proof.connect() as c:
        c.execute(text("SET SESSION sql_mode=''"))
        with pytest.raises(DBAPIError):
            insert(c, "😀" * 501)
        c.rollback()
        assert c.scalar(text("SELECT COUNT(*) FROM sys_file")) == 0

"""Phase-0 evidence, real MySQL only; never imports application models."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pymysql
import pytest

ROOT = Path(__file__).parent


def connect(database=None):
    password = (ROOT / ".env").read_text().strip().split("=", 1)[1]
    return pymysql.connect(
        host="127.0.0.1",
        port=57357,
        user="root",
        password=password,
        database=database,
        autocommit=False,
    )


def execute(connection, sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def load(connection, sql):
    delimiter = ";"
    buffer = ""
    for line in sql.splitlines():
        if line.startswith("--"):
            continue
        if line.startswith("DELIMITER "):
            delimiter = line.split()[1]
            continue
        buffer += line + "\n"
        if buffer.rstrip().endswith(delimiter):
            execute(connection, buffer.rstrip()[: -len(delimiter)])
            buffer = ""
    assert not buffer.strip()


@pytest.fixture
def database():
    admin = connect()
    assert execute(admin, "SELECT VERSION()")[0][0] == "5.7.44"
    name = "iterflow_proof_" + uuid4().hex
    execute(
        admin, f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
    )
    db = connect(name)
    try:
        yield db, name
    finally:
        db.close()
        execute(admin, f"DROP DATABASE `{name}`")
        admin.close()


def test_rejected_mirroring_guard_has_repeatable_read_bypass(database):
    db, name = database
    load(db, (ROOT / "schema.sql").read_text())
    execute(db, "INSERT INTO rd_version VALUES (1)")
    execute(db, "INSERT INTO rd_requirement(id) VALUES (1)")
    db.commit()
    execute(db, "SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    assert execute(db, "SELECT * FROM rd_version_requirement") == ()
    other = connect(name)
    execute(other, "INSERT INTO rd_version_requirement VALUES (1,1,1,1,DEFAULT)")
    other.commit()
    other.close()
    # The guard's consistent read uses a stale snapshot despite the UPDATE's current read.
    execute(db, "UPDATE rd_requirement SET current_version_id=NULL WHERE id=1")
    db.commit()
    assert execute(db, "SELECT current_version_id FROM rd_requirement") == ((None,),)
    assert execute(
        db, "SELECT version_id FROM rd_version_requirement WHERE active=1"
    ) == ((1,),)


def test_rejected_locking_guard_breaks_legal_migration(database):
    db, _ = database
    sql = (
        (ROOT / "schema.sql")
        .read_text()
        .replace(
            "WHERE requirement_id=OLD.id AND active=1;",
            "WHERE requirement_id=OLD.id AND active=1 FOR UPDATE;",
        )
    )
    load(db, sql)
    execute(db, "INSERT INTO rd_version VALUES (1)")
    execute(db, "INSERT INTO rd_requirement(id) VALUES (1)")
    db.commit()
    with pytest.raises(pymysql.err.OperationalError) as error:
        execute(db, "INSERT INTO rd_version_requirement VALUES (1,1,1,1,DEFAULT)")
    assert error.value.args[0] == 1442
    db.rollback()
    assert execute(db, "SELECT * FROM rd_version_requirement") == ()


def normalized(db):
    load(db, (ROOT / "normalized.sql").read_text())
    execute(db, "INSERT INTO rd_version VALUES (1),(2),(3)")
    execute(db, "INSERT INTO rd_requirement VALUES (1,1),(2,1),(3,1)")
    execute(db, "INSERT INTO rd_feedback VALUES (1,1),(2,1),(3,1)")
    db.commit()


def test_normalized_conversion_move_history_and_atomic_rollback(database):
    db, _ = database
    normalized(db)
    execute(db, "INSERT INTO rd_requirement_feedback VALUES (1,1,1,1,DEFAULT)")
    execute(db, "INSERT INTO rd_requirement_feedback VALUES (2,1,2,1,DEFAULT)")
    execute(db, "INSERT INTO rd_requirement_feedback VALUES (3,2,1,0,DEFAULT)")
    execute(db, "INSERT INTO rd_version_requirement VALUES (1,1,1,1,DEFAULT)")
    db.commit()
    assert execute(
        db, "SELECT main_requirement_id FROM rd_feedback_read ORDER BY id"
    ) == ((1,), (1,), (None,))
    execute(
        db, "UPDATE rd_requirement SET revision=revision+1 WHERE id=1 AND revision=1"
    )
    execute(db, "UPDATE rd_version_requirement SET active=0 WHERE id=1")
    execute(db, "INSERT INTO rd_version_requirement VALUES (2,1,2,1,DEFAULT)")
    db.commit()
    execute(db, "UPDATE rd_version_requirement SET active=0 WHERE id=2")
    execute(db, "INSERT INTO rd_version_requirement VALUES (3,1,3,1,DEFAULT)")
    db.commit()
    assert execute(
        db, "SELECT current_version_id,revision FROM rd_requirement_read WHERE id=1"
    ) == ((3, 2),)
    assert execute(
        db,
        "SELECT COUNT(*) FROM rd_version_requirement WHERE requirement_id=1 AND active=0",
    ) == ((2,),)
    # Inject failure after closing old relation and inserting a new parent.
    execute(db, "INSERT INTO rd_requirement VALUES (4,1)")
    execute(db, "UPDATE rd_version_requirement SET active=0 WHERE id=3")
    with pytest.raises(pymysql.err.IntegrityError):
        execute(db, "INSERT INTO rd_version_requirement VALUES (4,999,1,1,DEFAULT)")
    db.rollback()
    assert execute(
        db, "SELECT current_version_id FROM rd_requirement_read WHERE id=1"
    ) == ((3,),)
    assert execute(db, "SELECT * FROM rd_requirement WHERE id=4") == ()


@pytest.mark.parametrize(
    "sql,code",
    [
        ("UPDATE rd_requirement SET current_version_id=2 WHERE id=1", 1054),
        ("UPDATE rd_feedback SET main_requirement_id=2 WHERE id=1", 1054),
        ("INSERT INTO rd_version_requirement VALUES (2,1,2,1,DEFAULT)", 1062),
        ("INSERT INTO rd_requirement_feedback VALUES (2,2,1,1,DEFAULT)", 1062),
        ("INSERT INTO rd_version_requirement VALUES (2,999,1,1,DEFAULT)", 1452),
        ("UPDATE rd_version_requirement SET active=2 WHERE id=1", 1644),
        ("UPDATE rd_requirement_feedback SET is_primary=2 WHERE id=1", 1644),
        (
            "UPDATE rd_version_requirement SET active_requirement_id=NULL WHERE id=1",
            3105,
        ),
        ("UPDATE rd_requirement_read SET current_version_id=2 WHERE id=1", 1288),
    ],
)
def test_normalized_direct_sql_bypasses_rejected(database, sql, code):
    db, _ = database
    normalized(db)
    execute(db, "INSERT INTO rd_version_requirement VALUES (1,1,1,1,DEFAULT)")
    execute(db, "INSERT INTO rd_requirement_feedback VALUES (1,1,1,1,DEFAULT)")
    db.commit()
    with pytest.raises(pymysql.MySQLError) as error:
        execute(db, sql)
    assert error.value.args[0] == code
    db.rollback()
    assert execute(
        db, "SELECT current_version_id FROM rd_requirement_read WHERE id=1"
    ) == ((1,),)
    assert execute(
        db, "SELECT main_requirement_id FROM rd_feedback_read WHERE id=1"
    ) == ((1,),)


@pytest.mark.parametrize(
    "table,statement",
    [
        (
            "rd_version_requirement",
            "INSERT INTO rd_version_requirement VALUES ({id},2,{target},1,DEFAULT)",
        ),
        (
            "rd_requirement_feedback",
            "INSERT INTO rd_requirement_feedback VALUES ({id},{target},2,1,DEFAULT)",
        ),
    ],
)
def test_normalized_concurrent_association_has_one_winner(database, table, statement):
    db, name = database
    normalized(db)
    barrier = Barrier(2)

    def worker(i):
        connection = connect(name)
        try:
            barrier.wait(timeout=10)
            execute(connection, statement.format(id=10 + i, target=i + 1))
            connection.commit()
            return "committed"
        except pymysql.err.IntegrityError as error:
            connection.rollback()
            assert error.args[0] == 1062
            return "rejected"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(worker, range(2))) == ["committed", "rejected"]
    assert execute(db, f"SELECT COUNT(*) FROM {table}") == ((1,),)


def test_normalized_uncommitted_intermediate_step_invisible(database):
    db, name = database
    normalized(db)
    execute(db, "INSERT INTO rd_version_requirement VALUES (1,1,1,1,DEFAULT)")
    db.commit()
    execute(db, "UPDATE rd_version_requirement SET active=0 WHERE id=1")
    observer = connect(name)
    assert execute(
        observer, "SELECT current_version_id FROM rd_requirement_read WHERE id=1"
    ) == ((1,),)
    observer.close()
    execute(db, "INSERT INTO rd_version_requirement VALUES (2,1,2,1,DEFAULT)")
    db.rollback()
    assert execute(
        db, "SELECT current_version_id FROM rd_requirement_read WHERE id=1"
    ) == ((1,),)

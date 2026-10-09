from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.exceptions import ConflictError


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
if engine.dialect.name == "mysql":

    @event.listens_for(engine, "connect")
    def configure_mysql(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION foreign_key_checks = 1")
            cursor.execute("SET SESSION unique_checks = 1")
            cursor.execute("SET SESSION time_zone = '+00:00'")
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cursor.execute(
                "SET SESSION sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_ALL_TABLES,"
                "NO_ZERO_DATE,NO_ZERO_IN_DATE,"
                "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
            )


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except DBAPIError as exc:
        db.rollback()
        if db.get_bind().dialect.name == "mysql" and exc.orig is not None and exc.orig.args:
            if exc.orig.args[0] in {1062, 1205, 1213, 1451, 1452, 1644}:
                raise ConflictError("数据库约束或并发冲突。请刷新后重试", code=40940) from None
        raise
    finally:
        db.close()

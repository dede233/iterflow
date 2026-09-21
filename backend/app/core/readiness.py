from collections.abc import Callable
from uuid import uuid4

from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.services.storage import create_configured_storage


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def check_redis() -> None:
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
    try:
        client.ping()
    finally:
        client.close()


def check_storage() -> None:
    settings = get_settings()
    storage = create_configured_storage(settings)
    storage.ensure_bucket()
    if settings.storage_driver == "local":
        probe_key = f".readiness/{uuid4().hex}"
        storage.upload(probe_key, b"ok", content_type="text/plain")
        try:
            if not storage.exists(probe_key):
                raise OSError("local storage readiness probe was not persisted")
            with storage.open(probe_key) as stream:
                if stream.read() != b"ok":
                    raise OSError("local storage readiness probe could not be read")
        finally:
            storage.delete(probe_key)


def readiness_status() -> tuple[bool, dict[str, str]]:
    checks: dict[str, Callable[[], None]] = {
        "postgresql": check_database,
        "redis": check_redis,
        "storage": check_storage,
    }
    components: dict[str, str] = {}
    for name, check in checks.items():
        try:
            check()
        except Exception:
            components[name] = "unavailable"
        else:
            components[name] = "ok"
    return all(value == "ok" for value in components.values()), components

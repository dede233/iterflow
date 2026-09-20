from collections.abc import Callable

import boto3
from botocore.config import Config
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def check_redis() -> None:
    client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
    try:
        client.ping()
    finally:
        client.close()


def check_minio() -> None:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key.get_secret_value(),
        config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
    )
    client.head_bucket(Bucket=settings.minio_bucket)


def readiness_status() -> tuple[bool, dict[str, str]]:
    checks: dict[str, Callable[[], None]] = {
        "postgresql": check_database,
        "redis": check_redis,
        "minio": check_minio,
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

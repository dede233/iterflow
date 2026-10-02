import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://iterflow@localhost/iterflow_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "phase-zero-test-secret-that-is-at-least-32-characters")
os.environ.setdefault("JWT_ACCESS_TTL_MINUTES", "30")
os.environ.setdefault("JWT_REFRESH_TTL_DAYS", "14")
os.environ.setdefault("STORAGE_DRIVER", "local")
os.environ.setdefault("LOCAL_STORAGE_PATH", "./data/test-uploads")


def resolve_openapi_ref(document: dict, value: dict) -> dict:
    """Resolve one local OpenAPI reference in a schema value."""
    reference = value.get("$ref")
    if reference is None:
        return value
    if not reference.startswith("#/components/"):
        raise AssertionError(f"Expected a local component reference, got {reference!r}")
    resolved = document
    for part in reference.removeprefix("#/").split("/"):
        resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
    return resolved


def assert_revision_conflict(response, *, revision: int, updated_by: int) -> None:
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["code"] == 40910
    assert set(body["data"]) == {
        "current_revision",
        "current_updated_at",
        "current_updated_by",
    }
    assert body["data"]["current_revision"] == revision
    assert body["data"]["current_updated_by"] == updated_by
    assert datetime.fromisoformat(body["data"]["current_updated_at"])

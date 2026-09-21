from pathlib import Path

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/iterflow",
        redis_url="redis://localhost:6379/0",
        jwt_secret="storage-test-secret-that-is-at-least-32-characters",
        **overrides,
    )


def test_local_is_default_and_does_not_require_s3_configuration() -> None:
    settings = _settings()

    assert settings.storage_driver == "local"
    assert settings.s3_endpoint is None
    assert settings.s3_access_key is None
    assert settings.s3_secret_key is None


def test_storage_driver_is_case_insensitive_and_relative_path_uses_project_root() -> None:
    settings = _settings(storage_driver="S3", local_storage_path="./data/uploads")

    assert settings.storage_driver == "s3"
    assert settings.local_storage_root == (
        Path(__file__).resolve().parents[2] / "data" / "uploads"
    ).resolve()

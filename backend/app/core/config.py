from functools import lru_cache
from typing import ClassVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: ClassVar[str] = "迭程 IterFlow · 需求与版本协作管理系统"
    api_prefix: ClassVar[str] = "/api/v1"
    database_url: str = Field(min_length=1)
    redis_url: str = Field(min_length=1)
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_access_ttl_minutes: int = Field(default=30, gt=0)
    jwt_refresh_ttl_days: int = Field(default=14, gt=0)
    minio_endpoint: str = Field(min_length=1)
    minio_access_key: str = Field(min_length=1)
    minio_secret_key: SecretStr = Field(min_length=1)
    minio_bucket: str = Field(min_length=1)
    init_admin_username: str | None = None
    init_admin_password: SecretStr | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return ["http://localhost:5173", "http://localhost:8080"]


@lru_cache
def get_settings() -> Settings:
    # Required values are populated from the environment by pydantic-settings.
    return Settings()  # type: ignore[call-arg]

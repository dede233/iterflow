from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, SecretStr, field_validator
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
    storage_driver: Literal["local", "s3"] = "local"
    local_storage_path: Path = Path("./data/uploads")
    s3_endpoint: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    s3_bucket: str = Field(default="iterflow", min_length=1)
    s3_region: str = Field(default="us-east-1", min_length=1)
    init_admin_username: str | None = None
    init_admin_password: SecretStr | None = None

    @field_validator("storage_driver", mode="before")
    @classmethod
    def normalize_storage_driver(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("s3_endpoint", "s3_access_key", mode="before")
    @classmethod
    def blank_s3_values_are_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return ["http://localhost:5173", "http://localhost:8080"]

    @property
    def local_storage_root(self) -> Path:
        path = self.local_storage_path.expanduser()
        if path.is_absolute():
            return path.resolve()
        project_root = Path(__file__).resolve().parents[3]
        return (project_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    # Required values are populated from the environment by pydantic-settings.
    return Settings()  # type: ignore[call-arg]

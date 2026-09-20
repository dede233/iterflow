from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Requirements Version Management System"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    secret_key: str = "CHANGE_ME"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    database_url: str = "postgresql+psycopg://rvms:CHANGE_ME@localhost:5432/rvms"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "CHANGE_ME"
    s3_bucket: str = "rvms"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

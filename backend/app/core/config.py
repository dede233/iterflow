import re
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WECOM_MEMBER_USER_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.@-]*$"
WECOM_MEMBER_USER_ID_MAX_LENGTH = 64


def valid_wecom_member_user_id(value: str) -> bool:
    return len(value) <= WECOM_MEMBER_USER_ID_MAX_LENGTH and bool(
        re.fullmatch(WECOM_MEMBER_USER_ID_PATTERN, value)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", hide_input_in_errors=True
    )

    app_name: ClassVar[str] = "迭程 IterFlow · 需求与版本协作管理系统"
    api_prefix: ClassVar[str] = "/api/v1"
    app_env: Literal["development", "test", "production"] = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    allowed_hosts: str = ""
    trust_proxy_headers: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    enable_api_docs: bool = True
    build_sha: str = "unknown"
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
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr | None = None
    smtp_from: str = "iterflow@example.invalid"
    smtp_allowlist: str = ""
    wecom_enabled: bool = False
    wecom_corp_id: str = Field(default="", max_length=128)
    wecom_agent_id: int = Field(default=0, ge=0, le=2_147_483_647)
    wecom_agent_secret: SecretStr | None = None
    wecom_allowlist: str = ""
    app_public_url: str = "http://localhost:8080"
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

    @field_validator("wecom_corp_id", mode="before")
    @classmethod
    def normalize_wecom_corp_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def wecom_member_allowlist(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.wecom_allowlist.split(",") if item.strip())

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS cannot contain '*' with credentials enabled")
        if self.app_env == "production" and not self.allowed_host_list:
            raise ValueError("ALLOWED_HOSTS must be set in production")
        if self.app_env == "production" and "*" in self.allowed_host_list:
            raise ValueError("ALLOWED_HOSTS cannot contain '*' in production")
        if self.storage_driver == "s3" and bool(self.s3_access_key) != bool(self.s3_secret_key):
            raise ValueError("S3_ACCESS_KEY and S3_SECRET_KEY must be provided together")
        if self.smtp_enabled:
            public = urlsplit(self.app_public_url)
            if not self.smtp_host or not public.hostname or public.scheme not in {"http", "https"}:
                raise ValueError("SMTP_HOST and valid APP_PUBLIC_URL are required for mail")
            if self.app_env == "production" and (
                self.smtp_security == "none" or public.scheme != "https"
            ):
                raise ValueError("Production mail requires TLS and an HTTPS site URL")
            if self.app_env != "production" and not self.smtp_allowlist.strip():
                raise ValueError("Non-production mail requires an explicit SMTP_ALLOWLIST")
        if self.wecom_enabled:
            self._validate_wecom()
        return self

    def _validate_wecom(self) -> None:
        if (
            not self.wecom_corp_id
            or not self.wecom_agent_id
            or not self.wecom_agent_secret
            or not self.wecom_agent_secret.get_secret_value().strip()
        ):
            raise ValueError("WECOM_CORP_ID, WECOM_AGENT_ID and WECOM_AGENT_SECRET are required")
        try:
            public = urlsplit(self.app_public_url)
            port = public.port
        except ValueError:
            raise ValueError("WeCom requires a valid APP_PUBLIC_URL") from None
        if (
            public.scheme not in {"http", "https"}
            or not public.hostname
            or port == 0
            or public.username is not None
            or public.password is not None
            or len(self.app_public_url.encode("utf-8")) > 1024
            or any(
                char.isspace() or ord(char) < 32 or ord(char) == 127 for char in self.app_public_url
            )
            or any(marker in self.app_public_url for marker in {"?", "#", "\\"})
        ):
            raise ValueError("WeCom requires a valid APP_PUBLIC_URL base without credentials")
        if self.app_env == "production" and public.scheme != "https":
            raise ValueError("Production WeCom requires an HTTPS APP_PUBLIC_URL")
        if self.app_env != "production" and not self.wecom_member_allowlist:
            raise ValueError("Non-production WeCom requires an explicit WECOM_ALLOWLIST")
        if any(not valid_wecom_member_user_id(item) for item in self.wecom_member_allowlist):
            raise ValueError("WECOM_ALLOWLIST must contain valid WeCom member UserID values")

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

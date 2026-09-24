import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.cli.healthcheck import healthcheck_host
from app.core.config import Settings
from app.main import app


def _settings(**overrides: object) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://test@localhost/test",
        "redis_url": "redis://localhost:6379/0",
        "jwt_secret": "a-test-secret-that-is-longer-than-32-characters",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_hosts_are_required_and_wildcard_cors_is_rejected():
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        _settings(app_env="production")
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        _settings(cors_origins="*")
    settings = _settings(
        app_env="production", allowed_hosts="iterflow.example.com", cors_origins=""
    )
    assert settings.cors_origin_list == []
    assert settings.allowed_host_list == ["iterflow.example.com"]


def test_s3_credentials_must_be_paired():
    with pytest.raises(ValidationError, match="S3_ACCESS_KEY"):
        _settings(storage_driver="s3", s3_access_key="key")
    with pytest.raises(ValidationError, match="S3_ACCESS_KEY"):
        _settings(storage_driver="s3", s3_secret_key="secret")
    assert _settings(storage_driver="s3").s3_access_key is None


def test_healthcheck_uses_a_host_allowed_by_production_policy():
    exact = _settings(app_env="production", allowed_hosts="iterflow.example.test")
    assert healthcheck_host(exact) == "iterflow.example.test"
    wildcard = _settings(app_env="production", allowed_hosts="*.example.test")
    assert healthcheck_host(wildcard) == "health.example.test"


@pytest.mark.parametrize("request_id", ["bad\nheader", "bad@header", "x" * 65, "bad\trequest"])
def test_unsafe_request_id_is_replaced(request_id: str):
    response = TestClient(app).get("/health", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")


def test_proxy_ip_is_ignored_without_trust(monkeypatch):
    from app import main

    contexts = []
    original = main.set_audit_context
    monkeypatch.setattr(
        main, "set_audit_context", lambda context: (contexts.append(context), original(context))[1]
    )
    monkeypatch.setattr(main.settings, "trust_proxy_headers", False)
    response = TestClient(app).get("/health", headers={"X-Real-IP": "203.0.113.1"})
    assert response.status_code == 200
    assert response.json()["build_sha"] == "unknown"
    assert contexts[-1].ip_address != "203.0.113.1"

    monkeypatch.setattr(main.settings, "trust_proxy_headers", True)
    TestClient(app).get("/health", headers={"X-Real-IP": "203.0.113.1"})
    assert contexts[-1].ip_address == "203.0.113.1"
    TestClient(app).get("/health", headers={"X-Real-IP": "not-an-ip"})
    assert contexts[-1].ip_address != "not-an-ip"


def test_unexpected_exception_has_safe_error_and_request_id(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "readiness_status", lambda: 1 / 0)
    response = TestClient(app).get("/ready", headers={"X-Request-ID": "safe-id"})
    assert response.status_code == 500
    assert response.json() == {
        "code": 50000,
        "message": "服务器内部错误",
        "data": None,
        "request_id": "safe-id",
    }
    assert response.headers["X-Request-ID"] == "safe-id"
    assert "division" not in json.dumps(response.json())

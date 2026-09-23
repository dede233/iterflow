from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_upload_limit_and_timeout_are_aligned():
    nginx = (ROOT / "frontend/nginx.conf").read_text()
    feedback_api = (ROOT / "frontend/src/api/feedbacks.ts").read_text()
    assert "client_max_body_size 52m;" in nginx
    assert "proxy_read_timeout 120s;" in nginx
    assert "timeout: 120000" in feedback_api


def test_compose_initialization_gates_api_and_uses_named_uploads_volume():
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yml").read_text())
    services = compose["services"]
    assert (
        services["seed"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    )
    assert services["api"]["depends_on"]["seed"]["condition"] == "service_completed_successfully"
    assert "uploads:/app/data/uploads" in services["api"]["volumes"]
    assert compose["volumes"]["uploads"] is None


def test_web_defaults_to_localhost_and_images_are_patch_pinned():
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yml").read_text())
    assert compose["services"]["web"]["ports"] == [
        "${WEB_BIND_HOST:-127.0.0.1}:${WEB_PORT:-8080}:8080"
    ]
    assert compose["services"]["db"]["image"].startswith("postgres:17.")
    assert compose["services"]["redis"]["image"].startswith("redis:8.")

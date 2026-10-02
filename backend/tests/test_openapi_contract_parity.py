from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.main import app
from scripts.sync_openapi import generated_spec

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "spec" / "openapi-v1.7.yaml"
IGNORED_DOCUMENTATION_FIELDS = {
    "description",
    "summary",
    "operationId",
    "title",
    "example",
    "examples",
    "externalDocs",
    "tags",
}
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _resolve_local_refs(value: Any, document: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [_resolve_local_refs(item, document) for item in value]
    if not isinstance(value, dict):
        return value

    if "$ref" in value:
        reference = value["$ref"]
        assert reference.startswith("#/"), f"external OpenAPI ref is unsupported: {reference}"
        target: Any = document
        for token in reference[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            target = target[token]
        resolved = _resolve_local_refs(target, document)
        siblings = {key: child for key, child in value.items() if key != "$ref"}
        if siblings and isinstance(resolved, dict):
            return {**resolved, **_resolve_local_refs(siblings, document)}
        return resolved

    return {
        key: _resolve_local_refs(child, document)
        for key, child in value.items()
        if key not in IGNORED_DOCUMENTATION_FIELDS
    }


def _api_paths(document: dict[str, Any], *, runtime: bool) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for path, path_item in document["paths"].items():
        if runtime:
            assert path.startswith("/api/v1/")
            path = path.removeprefix("/api/v1")
        paths[path] = {
            method: operation
            for method, operation in path_item.items()
            if method.lower() in HTTP_METHODS
        }
    return paths


def _operation_contract(operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return _resolve_local_refs(
        {
            field: operation[field]
            for field in ("parameters", "requestBody", "responses", "security")
            if field in operation
        },
        spec,
    )


def test_v15_openapi_remains_available() -> None:
    assert (ROOT / "spec" / "openapi-v1.6.yaml").is_file()
    assert (ROOT / "spec" / "openapi-v1.5.yaml").is_file()
    assert (ROOT / "spec" / "需求与版本管理系统_V1.5_OpenAPI.yaml").is_file()


def test_runtime_openapi_matches_static_contract() -> None:
    static = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    runtime = app.openapi()
    assert static["info"]["version"] == runtime["info"]["version"]
    runtime_paths = _api_paths(runtime, runtime=True)
    static_paths = _api_paths(static, runtime=False)

    assert set(runtime_paths) == set(static_paths)
    for path in sorted(static_paths):
        assert set(runtime_paths[path]) == set(static_paths[path]), path
        for method in sorted(static_paths[path]):
            assert _operation_contract(runtime_paths[path][method], runtime) == _operation_contract(
                static_paths[path][method], static
            ), f"OpenAPI operation drift: {method.upper()} {path}"

    assert _resolve_local_refs(runtime["components"].get("schemas", {}), runtime) == (
        _resolve_local_refs(static["components"].get("schemas", {}), static)
    )
    assert _resolve_local_refs(runtime["components"].get("securitySchemes", {}), runtime) == (
        _resolve_local_refs(static["components"].get("securitySchemes", {}), static)
    )


def test_openapi_sync_generator_is_idempotent() -> None:
    canonical = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    assert generated_spec(canonical) == canonical


def test_requirement_create_conditional_authorization_is_documented() -> None:
    static = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    runtime_description = app.openapi()["paths"]["/api/v1/requirements"]["post"]["description"]
    static_description = static["paths"]["/requirements"]["post"]["description"]
    assert static_description == runtime_description
    for term in (
        "rd.requirement.create",
        "version_id",
        "version_revision",
        "rd.version.edit",
        "rd.requirement.view",
        "Version DataScope",
    ):
        assert term in static_description


def test_v16_revision_conflict_contract_covers_all_core_cas_routes() -> None:
    static = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    schemas = static["components"]["schemas"]
    assert schemas["RevisionConflictResponse"]["properties"]["code"]["const"] == 40910
    assert set(schemas["RevisionConflictData"]["required"]) == {
        "current_revision",
        "current_updated_at",
        "current_updated_by",
    }
    routes = {
        ("/feedbacks/{feedback_id}", "patch"),
        ("/feedbacks/{feedback_id}/status", "patch"),
        ("/feedbacks/{feedback_id}/convert", "post"),
        ("/requirements", "post"),
        ("/requirements/{requirement_id}", "patch"),
        ("/requirements/{requirement_id}/status", "patch"),
        ("/versions/{version_id}", "patch"),
        ("/versions/{version_id}/status", "patch"),
        ("/versions/{version_id}/requirements", "post"),
        ("/versions/{version_id}/requirements/{requirement_id}", "delete"),
        ("/versions/{version_id}/requirements/move", "post"),
        ("/versions/{version_id}/publish", "post"),
    }
    for path, method in routes:
        schema = static["paths"][path][method]["responses"]["409"]["content"]["application/json"][
            "schema"
        ]
        assert {part["$ref"] for part in schema["anyOf"]} == {
            "#/components/schemas/RevisionConflictResponse",
            "#/components/schemas/ErrorResponse",
        }
    check_schema = static["paths"]["/versions/{version_id}/publish/check"]["post"]["responses"][
        "409"
    ]["content"]["application/json"]["schema"]
    assert check_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_notification_v2_contract_is_personal_and_nonnegative() -> None:
    static = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    for path, method, schema, field in (
        ("/notifications/unread-count", "get", "NotificationUnreadCount", "unread_count"),
        ("/notifications/read-all", "post", "NotificationReadAllResult", "updated_count"),
    ):
        operation = static["paths"][path][method]
        assert operation["security"] == [{"bearerAuth": []}]
        assert "DataScope" in operation["description"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{schema}"
        }
        assert static["components"]["schemas"][schema]["required"] == [field]
        assert static["components"]["schemas"][schema]["properties"][field]["minimum"] == 0

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.main import app
from scripts.sync_openapi import generated_spec

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "spec" / "openapi-v1.5.yaml"
SECONDARY = ROOT / "spec" / "需求与版本管理系统_V1.5_OpenAPI.yaml"
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


def test_static_openapi_copies_are_identical() -> None:
    canonical = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    secondary = yaml.safe_load(SECONDARY.read_text(encoding="utf-8"))
    assert secondary == canonical


def test_runtime_openapi_matches_static_contract() -> None:
    static = yaml.safe_load(CANONICAL.read_text(encoding="utf-8"))
    runtime = app.openapi()
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

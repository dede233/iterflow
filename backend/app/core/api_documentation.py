"""Copy documentation annotations without changing runtime schema structure."""

from typing import Any


def apply_schema_labels(schema: dict[str, Any], labels: dict[str, Any]) -> None:
    for key in ("title", "description"):
        if key in labels:
            schema[key] = labels[key]
    for key in ("properties", "$defs"):
        for name, child in labels.get(key, {}).items():
            target = schema.get(key, {}).get(name)
            if isinstance(target, dict):
                apply_schema_labels(target, child)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict) and isinstance(labels.get(key), dict):
            apply_schema_labels(schema[key], labels[key])
    for key in ("anyOf", "allOf", "oneOf"):
        for target, child in zip(schema.get(key, []), labels.get(key, []), strict=False):
            apply_schema_labels(target, child)


def schema_labels(schema: dict[str, Any]) -> dict[str, Any]:
    result = {key: schema[key] for key in ("title", "description") if key in schema}
    for key in ("properties", "$defs"):
        if key in schema:
            result[key] = {name: schema_labels(child) for name, child in schema[key].items()}
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            result[key] = schema_labels(schema[key])
    for key in ("anyOf", "allOf", "oneOf"):
        if key in schema:
            result[key] = [schema_labels(child) for child in schema[key]]
    return result

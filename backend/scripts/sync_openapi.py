from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SPEC = ROOT / "spec" / "openapi-v1.5.yaml"
SECONDARY_SPEC = ROOT / "spec" / "需求与版本管理系统_V1.5_OpenAPI.yaml"
DOC_FIELDS = {
    "description",
    "externalDocs",
    "operationId",
    "summary",
    "tags",
    "deprecated",
}


def generated_spec(documentation: dict[str, Any]) -> dict[str, Any]:
    runtime = app.openapi()
    paths: dict[str, Any] = {}
    for runtime_path, runtime_path_item in runtime["paths"].items():
        path = runtime_path.removeprefix("/api/v1")
        documented_path_item = documentation.get("paths", {}).get(path, {})
        path_item = {
            key: value
            for key, value in runtime_path_item.items()
            if key.lower()
            not in {
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
            }
        }
        path_item.update(
            {
                key: documented_path_item[key]
                for key in {"summary", "description", "servers"}
                if key in documented_path_item
            }
        )
        path_item.update(
            {key: value for key, value in documented_path_item.items() if key.startswith("x-")}
        )
        for method, operation in runtime_path_item.items():
            documented_operation = documented_path_item.get(method, {})
            paths.setdefault(path, path_item)[method] = {
                **operation,
                **{
                    key: documented_operation[key]
                    for key in DOC_FIELDS
                    if key in documented_operation
                },
            }
    return {
        "openapi": runtime["openapi"],
        "info": documentation.get("info", runtime.get("info", {})),
        "servers": documentation.get("servers", [{"url": "/api/v1"}]),
        "tags": documentation.get("tags", runtime.get("tags", [])),
        "paths": paths,
        "components": runtime.get("components", {}),
    }


def main() -> None:
    documentation = yaml.safe_load(CANONICAL_SPEC.read_text(encoding="utf-8"))
    spec = generated_spec(documentation)
    serialized = yaml.safe_dump(
        spec,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    CANONICAL_SPEC.write_text(serialized, encoding="utf-8")
    SECONDARY_SPEC.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()

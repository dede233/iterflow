"""Bundle Chinese labels from the active contract without a runtime YAML dependency."""

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "backend" / "app" / "core" / "api_documentation.json"


def documentation_labels(contract: dict[str, Any]) -> dict[str, Any]:
    fields = {"summary", "description", "tags"}
    return {
        "info": contract["info"],
        "tags": contract.get("tags", []),
        "paths": {
            path: {
                method: {key: value for key, value in operation.items() if key in fields}
                for method, operation in operations.items()
            }
            for path, operations in contract["paths"].items()
        },
    }


if __name__ == "__main__":
    import yaml

    contract = yaml.safe_load((ROOT / "spec" / "openapi-development.yaml").read_text())
    TARGET.write_text(
        json.dumps(documentation_labels(contract), ensure_ascii=False, indent=2) + "\n"
    )

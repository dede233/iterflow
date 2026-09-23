import ast
import re
from pathlib import Path

from app.cli.seed import PERMISSIONS
from app.services.permission_catalog import PermissionCatalog

APP_DIR = Path(__file__).resolve().parents[1] / "app"
API_V1_DIR = APP_DIR / "api" / "v1"
PERMISSION_CODE = re.compile(
    r"^(?:dashboard\.view|(?:rd|sys)\.[a-z][a-z0-9_-]*\.[a-z][a-z0-9_.-]*)$"
)
FORBIDDEN_SQL_IMPORTS = {"select", "update", "delete", "func"}
FORBIDDEN_DB_CALLS = {"execute", "scalar", "scalars", "commit", "flush"}


def _permission_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and PERMISSION_CODE.fullmatch(node.value)
    }


def test_every_active_permission_is_seeded_and_every_orphan_is_deprecated() -> None:
    files = [path for path in APP_DIR.rglob("*.py")]
    runtime_files = [
        path
        for path in files
        if path not in {APP_DIR / "cli" / "seed.py", APP_DIR / "services" / "permission_catalog.py"}
    ]
    used = set().union(*(_permission_literals(path) for path in runtime_files))
    seeded = set(PERMISSIONS)
    deprecated = set(PermissionCatalog.DEPRECATED_REPLACEMENTS)
    replacements = set(PermissionCatalog.DEPRECATED_REPLACEMENTS.values())

    assert used <= seeded, f"runtime permissions missing from seed: {sorted(used - seeded)}"
    assert seeded - used <= deprecated, (
        f"seeded permissions have no runtime capability or deprecation: "
        f"{sorted(seeded - used - deprecated)}"
    )
    assert deprecated <= seeded
    assert replacements <= seeded
    assert "rd.requirement.version.move" not in used
    assert "rd.requirement.version.move" in deprecated
    assert PermissionCatalog.DEPRECATED_REPLACEMENTS["rd.requirement.version.move"] == (
        "rd.version.edit"
    )


def test_api_routers_do_not_own_sql_or_transaction_boundaries() -> None:
    violations: list[str] = []
    for path in sorted(API_V1_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "sqlalchemy" or node.module.startswith("sqlalchemy."):
                    forbidden = FORBIDDEN_SQL_IMPORTS.intersection(
                        alias.name for alias in node.names
                    )
                    if forbidden:
                        violations.append(f"{path.name}:{node.lineno}: imports {sorted(forbidden)}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy."):
                        violations.append(f"{path.name}:{node.lineno}: imports {alias.name}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "db"
                and node.func.attr in FORBIDDEN_DB_CALLS
            ):
                violations.append(f"{path.name}:{node.lineno}: calls db.{node.func.attr}()")

    assert not violations, "Router SQL/transaction boundary violations:\n" + "\n".join(violations)

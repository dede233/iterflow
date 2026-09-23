from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

from app.main import app
from app.services.editing_service import EditingService

# Central index of the static router gates. Data-scope and conditional child
# checks are documented alongside each route and exercised by API regression
# suites for the owning domain.
CORE_ROUTE_PERMISSION_MATRIX: dict[tuple[str, str], dict[str, Any]] = {
    ("GET", "/api/v1/feedbacks"): {
        "gates": [("any", ("rd.feedback.view",))],
        "scope": "SELF-other-feedback-404",
    },
    ("POST", "/api/v1/feedbacks"): {
        "gates": [("any", ("rd.feedback.create",))],
        "scope": "create-as-current-user",
    },
    ("POST", "/api/v1/feedbacks/{feedback_id}/convert"): {
        "gates": [("any", ("rd.feedback.convert",))],
        "conditional": {"LINK_EXISTING": "rd.requirement.view"},
        "scope": "target-requirement-SELF-404",
    },
    ("GET", "/api/v1/requirements/{requirement_id}/feedbacks"): {
        "gates": [("all", ("rd.requirement.view", "rd.feedback.view"))],
        "scope": "requirement-and-feedback-SELF-404-filter",
    },
    ("GET", "/api/v1/versions/{version_id}"): {
        "gates": [("any", ("rd.version.view",))],
        "scope": "SELF-other-version-404",
    },
    ("GET", "/api/v1/versions/{version_id}/requirements"): {
        "gates": [("all", ("rd.version.view", "rd.requirement.view"))],
        "scope": "version-and-requirement-SELF-filter",
    },
    ("POST", "/api/v1/versions/{version_id}/requirements"): {
        "gates": [("all", ("rd.version.edit", "rd.requirement.view"))],
        "scope": "version-and-requirement-SELF-404",
    },
    ("POST", "/api/v1/versions/{version_id}/requirements/move"): {
        "gates": [("all", ("rd.version.edit", "rd.requirement.view"))],
        "scope": "source-target-version-and-requirement-SELF-404",
    },
    ("DELETE", "/api/v1/versions/{version_id}/requirements/{requirement_id}"): {
        "gates": [("all", ("rd.version.edit", "rd.requirement.view"))],
        "scope": "version-and-requirement-SELF-404",
    },
    ("POST", "/api/v1/versions/{version_id}/publish"): {
        "gates": [("any", ("rd.version.publish",))],
        "scope": "SELF-other-version-404",
    },
    ("GET", "/api/v1/releases/{release_id}"): {
        "gates": [("any", ("rd.release.view",))],
        "scope": "release-parent-version-scope-404",
    },
    ("GET", "/api/v1/files/{file_id}/download"): {
        "gates": [("any", ("sys.file.download",))],
        "scope": "standalone-file-scope-and-attached-404",
    },
    ("DELETE", "/api/v1/files/{file_id}"): {
        "gates": [("any", ("sys.file.delete",))],
        "scope": "file-scope-before-attached-conflict",
    },
    ("GET", "/api/v1/audits"): {
        "gates": [("any", ("sys.audit.view",))],
        "scope": "underlying-entity-permission-and-scope",
    },
    ("GET", "/api/v1/users/{user_id}"): {
        "gates": [("any", ("sys.user.view",))],
        "scope": "SELF-other-user-403",
    },
    ("POST", "/api/v1/users"): {
        "gates": [("any", ("sys.user.create",)), ("any", ("sys.user.role.assign",))],
        "scope": "ALL-required-403",
    },
    ("GET", "/api/v1/roles"): {
        "gates": [("any", ("sys.role.view", "sys.role.manage", "sys.user.role.assign"))],
        "scope": "ALL-required-403",
    },
    ("POST", "/api/v1/roles"): {
        "gates": [("any", ("sys.role.manage",))],
        "scope": "ALL-required-403",
    },
}


def _calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _calls(dependency)


def _api_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        candidates = getattr(route, "effective_candidates", None)
        if candidates is None:
            continue
        for candidate in candidates():
            if getattr(candidate, "dependant", None) is not None:
                yield candidate
            else:
                yield from _api_routes([candidate])


def test_core_route_permission_matrix_matches_runtime_dependency_gates() -> None:
    actual: dict[tuple[str, str], list[tuple[str, tuple[str, ...]]]] = {}
    for route in _api_routes(app.routes):
        gates = {
            metadata
            for call in _calls(route.dependant)
            if (metadata := getattr(call, "__iterflow_required_permissions__", None))
        }
        for method in route.methods or ():
            actual[(method, route.path_format)] = sorted(gates)

    for key, expectation in CORE_ROUTE_PERMISSION_MATRIX.items():
        assert key in actual, f"missing protected route in matrix: {key}"
        for gate in expectation["gates"]:
            assert gate in actual[key], f"permission gate drift at {key}: {expectation}"
        assert expectation["scope"], f"scope behavior must be explicitly documented for {key}"

    editing_permissions = {
        entity_type.value: permissions
        for entity_type, permissions in EditingService.MUTATION_PERMISSIONS.items()
    }
    assert editing_permissions == {
        "FEEDBACK": {"rd.feedback.edit", "rd.feedback.convert"},
        "REQUIREMENT": {"rd.requirement.edit", "rd.requirement.status"},
        "VERSION": {"rd.version.edit", "rd.version.status", "rd.version.publish"},
    }

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.deps import current_user
from app.api.v1.router import api_router
from app.core.audit_context import AuditContext, reset_audit_context, set_audit_context
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.readiness import readiness_status
from app.schemas.common import ErrorResponse

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


def _dependency_calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependency_calls(dependency)


def _effective_api_routes(routes):
    """Flatten FastAPI's lazily included routers into effective route contexts."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue

        effective_candidates = getattr(route, "effective_candidates", None)
        if effective_candidates is None:
            continue
        for candidate in effective_candidates():
            if isinstance(candidate, APIRoute) or getattr(candidate, "dependant", None):
                yield candidate
            else:
                yield from _effective_api_routes([candidate])


def _error_response(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
    }


def custom_openapi() -> dict:
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema.setdefault("components", {}).setdefault("schemas", {})["ErrorResponse"] = (
        ErrorResponse.model_json_schema()
    )

    for route in _effective_api_routes(app.routes):
        path = getattr(route, "path_format", route.path_format)
        operations = schema.get("paths", {}).get(path, {})
        calls = set(_dependency_calls(route.dependant))
        authenticated = current_user in calls
        has_permission_gate = any(
            getattr(call, "__iterflow_required_permissions__", None) is not None for call in calls
        )
        for method in route.methods or ():
            operation = operations.get(method.lower())
            if operation is None:
                continue
            responses = operation.setdefault("responses", {})
            if authenticated:
                responses.setdefault("401", _error_response("未登录或登录凭证不可用"))
            if has_permission_gate:
                responses.setdefault("403", _error_response("无权执行该操作"))

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = (
        supplied_request_id
        if supplied_request_id and len(supplied_request_id) <= 64
        else f"req_{uuid4().hex[:16]}"
    )
    request.state.request_id = request_id
    user_agent = request.headers.get("User-Agent")
    client_ip = request.client.host if request.client else None
    token = set_audit_context(
        AuditContext(
            request_id=request_id,
            ip_address=client_ip[:64] if client_ip else None,
            user_agent=user_agent[:512] if user_agent else None,
        )
    )
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_audit_context(token)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok", "version": "1.5.0"}


@app.get("/ready", include_in_schema=False)
def ready():
    is_ready, components = readiness_status()
    payload = {
        "status": "ok" if is_ready else "unavailable",
        "components": components,
    }
    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload

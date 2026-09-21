from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.audit_context import AuditContext, reset_audit_context, set_audit_context
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.readiness import readiness_status

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


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.5.0"}


@app.get("/ready")
def ready():
    is_ready, components = readiness_status()
    payload = {
        "status": "ok" if is_ready else "unavailable",
        "components": components,
    }
    if not is_ready:
        return JSONResponse(status_code=503, content=payload)
    return payload

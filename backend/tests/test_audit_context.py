import asyncio
from unittest.mock import MagicMock

from fastapi import Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.audit_context import (
    AuditContext,
    audit_context,
    get_audit_context,
    set_audit_operator,
)
from app.core.security import create_access_token
from app.main import request_id_middleware
from app.models.entities import User
from app.models.enums import UserStatus
from app.services.audit_service import AuditService


def test_audit_service_populates_request_context_automatically():
    db = MagicMock(spec=Session)
    context = AuditContext(
        request_id="req_audit_test",
        ip_address="127.0.0.1",
        user_agent="IterFlow-Test/1.0",
        operator_id=42,
    )

    with audit_context(context):
        AuditService(db).log(
            "REQUIREMENT",
            7,
            "UPDATE",
            before={"revision": 1},
            after={"revision": 2},
        )

    operation_log = db.add.call_args.args[0]
    assert operation_log.operator_id == 42
    assert operation_log.request_id == "req_audit_test"
    assert operation_log.ip_address == "127.0.0.1"
    assert operation_log.user_agent == "IterFlow-Test/1.0"
    assert operation_log.before_data == {"revision": 1}
    assert operation_log.after_data == {"revision": 2}
    assert get_audit_context() == AuditContext()


def test_request_middleware_binds_and_resets_transport_audit_context():
    captured: AuditContext | None = None

    async def call_next(_: Request) -> Response:
        nonlocal captured
        captured = get_audit_context()
        return Response()

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [
                (b"x-request-id", b"req_from_client"),
                (b"user-agent", b"IterFlow-Agent/1.0"),
            ],
            "client": ("192.0.2.10", 43100),
        }
    )

    response = asyncio.run(request_id_middleware(request, call_next))

    assert captured == AuditContext(
        request_id="req_from_client",
        ip_address="192.0.2.10",
        user_agent="IterFlow-Agent/1.0",
    )
    assert response.headers["X-Request-ID"] == "req_from_client"
    assert get_audit_context() == AuditContext()


def test_request_without_context_headers_gets_generated_request_id():
    captured: AuditContext | None = None

    async def call_next(_: Request) -> Response:
        nonlocal captured
        captured = get_audit_context()
        return Response()

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
            "client": ("192.0.2.11", 43101),
        }
    )

    asyncio.run(request_id_middleware(request, call_next))

    assert captured is not None
    assert captured.operator_id is None
    assert captured.request_id is not None
    assert len(captured.request_id) <= 64
    assert get_audit_context() == AuditContext()


def test_concurrent_audit_contexts_are_isolated():
    async def worker(request_id: str, operator_id: int) -> AuditContext:
        with audit_context(AuditContext(request_id=request_id, operator_id=operator_id)):
            await asyncio.sleep(0)
            return get_audit_context()

    async def run_workers() -> list[AuditContext]:
        return await asyncio.gather(worker("req_one", 1), worker("req_two", 2))

    contexts = asyncio.run(run_workers())

    assert contexts == [
        AuditContext(request_id="req_one", operator_id=1),
        AuditContext(request_id="req_two", operator_id=2),
    ]
    assert get_audit_context() == AuditContext()


def test_current_user_confirms_operator_after_database_validation():
    db = MagicMock(spec=Session)
    db.get.return_value = User(id=31, username="auditor", status=UserStatus.ACTIVE)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(31),
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/me",
            "headers": [],
            "client": ("192.0.2.12", 43102),
        }
    )

    with audit_context(AuditContext(request_id="req_confirmed")):
        authenticated = current_user(request=request, credentials=credentials, db=db)
        context = get_audit_context()

    assert authenticated.id == 31
    assert context.operator_id == 31
    assert context.request_id == "req_confirmed"
    assert get_audit_context() == AuditContext()


def test_verified_operator_propagates_from_sync_worker_context():
    async def bind_from_worker() -> AuditContext:
        with audit_context(AuditContext(request_id="req_worker")):
            await asyncio.to_thread(set_audit_operator, 44)
            return get_audit_context()

    context = asyncio.run(bind_from_worker())

    assert context == AuditContext(request_id="req_worker", operator_id=44)
    assert get_audit_context() == AuditContext()

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(slots=True)
class AuditContext:
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    operator_id: int | None = None


_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def get_audit_context() -> AuditContext:
    """Return the request-owned audit context, or an empty context outside a scope."""
    return _audit_context.get() or AuditContext()


def set_audit_context(context: AuditContext) -> Token[AuditContext | None]:
    return _audit_context.set(context)


def reset_audit_context(token: Token[AuditContext | None]) -> None:
    _audit_context.reset(token)


def set_audit_operator(operator_id: int) -> None:
    """Confirm the authenticated operator inside the active request context."""
    context = _audit_context.get()
    if context is None:
        _audit_context.set(AuditContext(operator_id=operator_id))
    else:
        # Sync FastAPI dependencies run in a copied Context. Each request owns a
        # unique AuditContext object, so mutating it propagates the verified user
        # to later sync service calls without crossing request boundaries.
        context.operator_id = operator_id


@contextmanager
def audit_context(context: AuditContext) -> Iterator[AuditContext]:
    """Create an isolated audit scope for jobs, scripts, and tests."""
    token = set_audit_context(context)
    try:
        yield context
    finally:
        reset_audit_context(token)

from sqlalchemy.orm import Session

from app.core.audit_context import get_audit_context
from app.models.entities import OperationLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        entity_type: str,
        entity_id: int | None,
        action: str,
        *,
        before=None,
        after=None,
    ):
        context = get_audit_context()
        self.db.add(
            OperationLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                operator_id=context.operator_id,
                request_id=context.request_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                before_data=before,
                after_data=after,
            )
        )

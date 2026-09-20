from sqlalchemy.orm import Session

from app.models.entities import OperationLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        entity_type: str,
        entity_id: int | None,
        action: str,
        operator_id: int | None,
        before=None,
        after=None,
        request_id: str | None = None,
        ip_address: str | None = None,
    ):
        self.db.add(
            OperationLog(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                operator_id=operator_id,
                request_id=request_id,
                ip_address=ip_address,
                before_data=before,
                after_data=after,
            )
        )

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_business_no(db: Session, model, column, prefix: str) -> str:
    """Small-installation baseline number generator.

    For high concurrency, replace with a PostgreSQL sequence table or dedicated ID service.
    """
    today = datetime.now(UTC).strftime("%Y%m%d")
    like = f"{prefix}-{today}-%"
    max_value = db.scalar(select(func.max(column)).where(column.like(like)))
    seq = int(max_value.rsplit("-", 1)[1]) + 1 if max_value else 1
    return f"{prefix}-{today}-{seq:04d}"

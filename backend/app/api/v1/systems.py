from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import BusinessModule, BusinessSystem, User

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("")
def list_systems(
    db: Session = Depends(get_db), user: User = Depends(require_permission("sys.system.view"))
):
    systems = db.scalars(
        select(BusinessSystem)
        .where(BusinessSystem.enabled.is_(True))
        .order_by(BusinessSystem.sort_order)
    ).all()
    modules = db.scalars(
        select(BusinessModule)
        .where(BusinessModule.enabled.is_(True))
        .order_by(BusinessModule.sort_order)
    ).all()
    return {"systems": systems, "modules": modules}

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.schemas.system import BusinessSystemCatalogOut
from app.services.system_query_service import SystemQueryService

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("", response_model=BusinessSystemCatalogOut)
def list_systems(
    db: Session = Depends(get_db), user: User = Depends(require_permission("sys.system.view"))
):
    return SystemQueryService(db).list_enabled()

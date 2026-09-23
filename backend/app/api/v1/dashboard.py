from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.schemas.dashboard import DashboardOverviewOut
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewOut,
    summary="获取权限感知的业务概览",
    description=(
        "Requires dashboard.view. Each domain section also requires its matching "
        "rd.*.view permission or wildcard. Unauthorized sections are null and all "
        "statistics follow the current user's SELF/ALL DataScope."
    ),
)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("dashboard.view")),
) -> DashboardOverviewOut:
    return DashboardService(db).overview(user.id)

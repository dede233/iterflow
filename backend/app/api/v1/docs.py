from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.services.api_documentation_service import ApiDocumentationService

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("/openapi", responses=api_error_responses(401, 403))
def api_documentation(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    return ApiDocumentationService(db).read(user, request.app.openapi())

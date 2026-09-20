from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.database import get_db
from app.models.entities import User
from app.repositories.requirement_repository import RequirementRepository
from app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementStatusChange, RequirementMoveVersion
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.get("")
def list_requirements(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.view"))):
    items, total = RequirementRepository(db).list(page, page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post("")
def create_requirement(payload: RequirementCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.create"))):
    return RequirementService(db).create(payload, user.id)


@router.get("/{requirement_id}")
def get_requirement(requirement_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.view"))):
    return RequirementRepository(db).get(requirement_id)


@router.patch("/{requirement_id}")
def update_requirement(requirement_id: int, payload: RequirementUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.edit"))):
    return RequirementService(db).update(requirement_id, payload, user.id)


@router.patch("/{requirement_id}/status")
def change_status(requirement_id: int, payload: RequirementStatusChange, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.status"))):
    return RequirementService(db).change_status(requirement_id, payload, user.id)


@router.post("/{requirement_id}/move-version")
def move_version(requirement_id: int, payload: RequirementMoveVersion, db: Session = Depends(get_db), user: User = Depends(require_permission("rd.requirement.version.move"))):
    return RequirementService(db).move_version(requirement_id, payload, user.id)

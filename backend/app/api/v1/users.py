from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.database import get_db
from app.core.security import hash_password
from app.models.entities import User, UserRole
from app.schemas.user import UserCreate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current: User = Depends(require_permission("sys.user.view"))):
    items = db.scalars(select(User).order_by(User.id.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items": items, "page": page, "page_size": page_size}


@router.post("")
def create_user(payload: UserCreate, db: Session = Depends(get_db), current: User = Depends(require_permission("sys.user.create"))):
    item = User(username=payload.username, display_name=payload.display_name, email=payload.email, password_hash=hash_password(payload.password), created_by=current.id, updated_by=current.id)
    db.add(item); db.flush()
    for role_id in payload.role_ids:
        db.add(UserRole(user_id=item.id, role_id=role_id))
    db.commit(); db.refresh(item)
    return item


@router.patch("/{user_id}/status")
def set_status(user_id: int, status: str, db: Session = Depends(get_db), current: User = Depends(require_permission("sys.user.status"))):
    item=db.get(User,user_id)
    if item:
        item.status=status; item.updated_by=current.id; item.revision+=1; db.commit(); db.refresh(item)
    return item

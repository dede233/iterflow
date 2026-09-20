from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.exceptions import ConflictError
from app.core.security import hash_password
from app.models.entities import User, UserRole
from app.schemas.user import UserCreate, UserOut, UserPage, UserStatusChange
from app.services.audit_service import AuditService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserPage)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.view")),
):
    items = db.scalars(
        select(User).order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [UserOut.model_validate(item).model_dump() for item in items],
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.create")),
):
    item = User(
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        created_by=current.id,
        updated_by=current.id,
    )
    db.add(item)
    db.flush()
    for role_id in payload.role_ids:
        db.add(UserRole(user_id=item.id, role_id=role_id))
    AuditService(db).log(
        "USER",
        item.id,
        "CREATE",
        current.id,
        after={"username": item.username, "role_ids": payload.role_ids},
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{user_id}/status", response_model=UserOut | None)
def set_status(
    user_id: int,
    payload: UserStatusChange,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("sys.user.status")),
):
    item = db.get(User, user_id)
    if item is None:
        return None
    previous_status = item.status
    updated = cast(
        CursorResult[Any],
        db.execute(
            update(User)
            .where(User.id == user_id, User.revision == payload.revision)
            .values(
                status=payload.status,
                updated_by=current.id,
                revision=User.revision + 1,
            )
        ),
    )
    if not updated.rowcount:
        db.refresh(item)
        raise ConflictError("用户已被其他用户修改", {"current_revision": item.revision})
    AuditService(db).log(
        "USER",
        user_id,
        "STATUS_CHANGE",
        current.id,
        before={"status": previous_status},
        after={"status": payload.status},
    )
    db.commit()
    db.refresh(item)
    return item

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.entities import User
from app.schemas.auth import (
    AuthMe,
    ChangePasswordRequest,
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    TokenPair,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return AuthService(db).login(payload.username, payload.password)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService(db).logout(payload.refresh_token)


@router.post("/change-password", response_model=TokenPair)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return AuthService(db).change_password(user, payload.current_password, payload.new_password)


@router.get("/me", response_model=AuthMe)
def me(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return AuthService(db).me(user)

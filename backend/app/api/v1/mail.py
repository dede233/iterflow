from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.core.exceptions import PermissionDenied
from app.models.entities import User
from app.repositories.user_repository import UserRepository
from app.schemas.mail import (
    DeliveryOut,
    DeliveryRetry,
    EmailUnbindRequest,
    EmailVerificationConfirm,
    EmailVerificationRequest,
    MailNoticeAcknowledge,
    MailPreferenceChange,
    MailPreferencesOut,
)
from app.services.delivery_service import DeliveryService
from app.services.mail_preferences_service import MailPreferencesService

router = APIRouter(tags=["mail"])


@router.get("/me/mail-preferences", response_model=MailPreferencesOut)
def get_mail_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return MailPreferencesService(db).get(user)


@router.put("/me/mail-preferences", response_model=MailPreferencesOut)
def change_mail_preferences(
    payload: MailPreferenceChange, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return MailPreferencesService(db).change(user, payload.revision, payload.mode)


@router.post(
    "/me/mail-notice/acknowledge",
    response_model=MailPreferencesOut,
    responses=api_error_responses(409),
)
def acknowledge_mail_notice(
    payload: MailNoticeAcknowledge,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return MailPreferencesService(db).acknowledge_notice(user, payload.revision)


@router.post(
    "/me/email-unbind",
    response_model=MailPreferencesOut,
    responses=api_error_responses(409),
    summary="取消绑定当前账号的通知邮箱",
)
def unbind_email(
    payload: EmailUnbindRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return MailPreferencesService(db).unbind(user, payload.revision)


@router.post("/me/email-verification", response_model=MailPreferencesOut)
def request_email_verification(
    payload: EmailVerificationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return MailPreferencesService(db).request(user, payload.revision, str(payload.email))


@router.post("/me/email-verification/confirm", response_model=MailPreferencesOut)
def confirm_email_verification(
    payload: EmailVerificationConfirm,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return MailPreferencesService(db).confirm(user, payload.revision, payload.code)


def mail_admin(
    db: Session = Depends(get_db), user: User = Depends(require_permission("sys.user.edit"))
):
    if not UserRepository(db).can_view_api_docs(user.id):
        raise PermissionDenied("仅管理员或研发负责人可管理投递")
    return user


@router.get("/admin/mail-deliveries", response_model=list[DeliveryOut])
def list_mail_deliveries(
    page: int = Query(1, ge=1),
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(mail_admin),
):
    return DeliveryService(db).list_deliveries(page, status)


@router.post("/admin/mail-deliveries/{delivery_id}/retry", response_model=DeliveryOut)
def retry_mail_delivery(
    delivery_id: str,
    payload: DeliveryRetry,
    db: Session = Depends(get_db),
    user: User = Depends(mail_admin),
):
    return DeliveryService(db).retry(delivery_id, payload.attempts)

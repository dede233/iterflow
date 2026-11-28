from fastapi import APIRouter, Depends, Query, Response
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
    MailDeliveryDetail,
    MailDeliveryKind,
    MailDeliveryPage,
    MailDeliveryRecipientPage,
    MailDeliveryResend,
    MailDeliveryStatus,
    MailNoticeAcknowledge,
    MailPreferenceChange,
    MailPreferencesOut,
)
from app.services.delivery_service import DeliveryService
from app.services.mail_delivery_monitor_service import MailDeliveryMonitorService
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


@router.get(
    "/admin/mail-delivery-monitor",
    response_model=MailDeliveryPage,
    responses=api_error_responses(403),
    summary="查看全局邮件投递记录",
    description=(
        "启用的内置 SUPER_ADMIN 或具有原邮件管理权限的账号可查看协作通知及邮箱验证的投递记录。"
        "原邮件管理权限要求启用的内置管理员或研发负责人角色及 sys.user.edit 权限。"
        "SENT 表示 SMTP 服务接受了邮件。收件及阅读状态未知。"
    ),
)
def list_mail_delivery_monitor(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: MailDeliveryStatus | None = None,
    kind: MailDeliveryKind | None = None,
    user_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MailDeliveryPage:
    return MailDeliveryMonitorService(db).list(
        user, page=page, page_size=page_size, status=status, kind=kind, user_id=user_id
    )


@router.get(
    "/admin/mail-delivery-monitor/recipients",
    response_model=MailDeliveryRecipientPage,
    responses=api_error_responses(403),
    summary="查找邮件投递接收账号",
    description=(
        "权限与全局邮件投递记录一致。"
        "启用的内置 SUPER_ADMIN 或具有 sys.user.view 和 ALL 数据范围的账号可查询全部账号。"
        "其他具备投递查看权限的账号可查询有邮件投递记录的接收账号。支持按姓名或用户名搜索。"
    ),
)
def list_mail_delivery_recipients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", max_length=100),
    selected_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MailDeliveryRecipientPage:
    return MailDeliveryMonitorService(db).list_recipients(
        user, page=page, page_size=page_size, keyword=keyword, selected_id=selected_id
    )


@router.get(
    "/admin/mail-delivery-monitor/{delivery_id}",
    response_model=MailDeliveryDetail,
    responses={
        **api_error_responses(403, 404, descriptions={404: "邮件投递记录不存在"}),
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "禁止缓存邮件投递详情",
                    "schema": {"type": "string"},
                },
            },
        },
    },
    summary="查看邮件投递详情",
    description=(
        "查看权限与全局邮件投递记录一致。"
        "返回投递时收件地址的脱敏值及原事件的标签和时间。每次查看均记录审计。"
    ),
)
def get_mail_delivery_detail(
    delivery_id: str,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MailDeliveryDetail:
    response.headers["Cache-Control"] = "private, no-store"
    return MailDeliveryMonitorService(db).get_detail(user, delivery_id)


@router.post(
    "/admin/mail-delivery-monitor/{delivery_id}/resend",
    status_code=204,
    response_class=Response,
    response_description="已加入邮件投递队列",
    responses=api_error_responses(
        403,
        404,
        409,
        descriptions={
            403: "无手动重发权限",
            404: "邮件投递记录不存在",
            409: "投递状态已变化或不再满足重发条件",
        },
    ),
    summary="手动重发邮件",
)
def resend_mail_delivery(
    delivery_id: str,
    payload: MailDeliveryResend,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response:
    MailDeliveryMonitorService(db).resend(user, delivery_id, payload.resend_token)
    return Response(status_code=204)


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

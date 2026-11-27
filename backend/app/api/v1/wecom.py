from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.wecom import WecomBindingChange, WecomPreferenceChange, WecomPreferencesOut
from app.services.wecom_preferences_service import WecomPreferencesService

router = APIRouter()
_CONFLICT = {409: "绑定、偏好或 revision 冲突"}


@router.get(
    "/me/wecom-preferences",
    response_model=WecomPreferencesOut,
    tags=["Notification"],
    summary="查看个人企业微信通知设置",
    operation_id="get_wecom_preferences",
    responses=api_error_responses(403),
)
def get_wecom_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return WecomPreferencesService(db).get(user.id)


@router.put(
    "/me/wecom-preferences",
    response_model=WecomPreferencesOut,
    tags=["Notification"],
    summary="调整个人企业微信通知偏好",
    operation_id="change_wecom_preferences",
    responses=api_error_responses(403, 409, descriptions=_CONFLICT),
)
def change_wecom_preferences(
    payload: WecomPreferenceChange,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return WecomPreferencesService(db).change(user.id, payload.revision, payload.mode)


@router.get(
    "/users/{user_id}/wecom-binding",
    response_model=WecomPreferencesOut,
    tags=["System"],
    summary="查看企业微信成员绑定",
    operation_id="get_user_wecom_binding",
    responses=api_error_responses(404),
)
def get_user_wecom_binding(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.user.edit")),
):
    return WecomPreferencesService(db).get_binding(user.id, user_id)


@router.put(
    "/users/{user_id}/wecom-binding",
    response_model=WecomPreferencesOut,
    tags=["System"],
    summary="更新企业微信成员绑定",
    operation_id="change_user_wecom_binding",
    responses=api_error_responses(404, 409, descriptions=_CONFLICT),
)
def change_user_wecom_binding(
    user_id: int,
    payload: WecomBindingChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("sys.user.edit")),
):
    return WecomPreferencesService(db).change_binding(
        user.id, user_id, payload.revision, payload.member_user_id
    )

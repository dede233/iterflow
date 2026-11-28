from typing import Annotated, BinaryIO

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_any_permission
from app.api.openapi import api_error_responses, api_revision_conflict_responses
from app.core.database import get_db
from app.core.exceptions import AppError
from app.domain.ad_production_permissions import AD_PRODUCTION_PERMISSIONS
from app.models.entities import FileObject, User
from app.models.enums import AdProductionKind, AdProductionStatus
from app.schemas.ad_production import (
    AdProductionCreateForm,
    AdProductionDesignerOption,
    AdProductionOut,
    AdProductionPage,
    AdProductionStatusChange,
    AdProductionTimestamp,
    AdProductionUpdateForm,
    AdWorkDate,
)
from app.schemas.entity_actions import EntityDelete, EntityDeleted
from app.services.ad_production_service import IMAGE_MEDIA_TYPES, AdProductionService

require_ad_production_view = require_any_permission(
    *(codes.view for codes in AD_PRODUCTION_PERMISSIONS.values())
)
PositivePathId = Annotated[int, Path(ge=1)]
IMAGE_RESPONSES = {
    **api_error_responses(403, 404, 422),
    200: {"content": {media: {} for media in IMAGE_MEDIA_TYPES}},
}


class AdProductionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = [{"loc": error["loc"], "msg": error["msg"]} for error in exc.errors()]
                raise AppError(42290, "请求参数或业务数据无效", 422, {"errors": errors}) from exc

        return handle


router = APIRouter(prefix="/ad-productions", tags=["ad-productions"], route_class=AdProductionRoute)


async def _update_supplies_content_format(request: Request) -> bool:
    form = await request.form()
    if "kind" in form:
        raise AppError(42290, "设计申请类型不能修改", 422, {"field": "kind"})
    # FastAPI fills defaults before validating multipart models.
    return "content_format" in form


async def _validate_cc_multipart_field(request: Request) -> None:
    values = (await request.form()).getlist("cc_user_ids")
    if len(values) > 1 or values == [""]:
        raise AppError(42290, "抄送账号必须为 JSON 数组", 422, {"field": "cc_user_ids"})


@router.get(
    "",
    response_model=AdProductionPage,
    operation_id="list_ad_productions",
    responses=api_error_responses(422),
)
def list_ad_productions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=100),
    kind: AdProductionKind = Query(AdProductionKind.MATERIAL),
    status: AdProductionStatus | None = Query(None),
    date_from: AdWorkDate | None = Query(None),
    date_to: AdWorkDate | None = Query(None),
    published_from: AdProductionTimestamp | None = Query(None),
    published_before: AdProductionTimestamp | None = Query(None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> AdProductionPage:
    return AdProductionService(db).listing(
        actor,
        page=page,
        page_size=page_size,
        keyword=keyword,
        kind=kind,
        status=status,
        date_from=date_from,
        date_to=date_to,
        published_from=published_from,
        published_before=published_before,
    )


@router.post(
    "",
    response_model=AdProductionOut,
    status_code=201,
    operation_id="create_ad_production",
    responses=api_error_responses(422),
    dependencies=[Depends(_validate_cc_multipart_field)],
)
def create_ad_production(
    payload: Annotated[AdProductionCreateForm, Form(media_type="multipart/form-data")],
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> AdProductionOut:
    return AdProductionService(db).create(payload, actor)


@router.get(
    "/designer-options",
    response_model=list[AdProductionDesignerOption],
    operation_id="list_ad_production_designers",
    responses=api_error_responses(422),
)
def list_ad_production_designers(
    kind: AdProductionKind = Query(AdProductionKind.MATERIAL),
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> list[AdProductionDesignerOption]:
    return AdProductionService(db).designer_options(actor, kind)


@router.get(
    "/cc-options",
    response_model=list[AdProductionDesignerOption],
    operation_id="list_ad_production_cc_options",
    responses=api_error_responses(404, 422),
)
def list_ad_production_cc_options(
    kind: AdProductionKind = Query(AdProductionKind.MATERIAL),
    ad_id: int | None = Query(None, ge=1),
    keyword: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> list[AdProductionDesignerOption]:
    return AdProductionService(db).cc_options(actor, kind=kind, ad_id=ad_id, keyword=keyword)


@router.get(
    "/{ad_id}",
    response_model=AdProductionOut,
    operation_id="get_ad_production",
    responses=api_error_responses(403, 404, 422),
)
def get_ad_production(
    ad_id: PositivePathId,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
) -> AdProductionOut:
    return AdProductionService(db).get(ad_id, actor)


@router.patch(
    "/{ad_id}",
    response_model=AdProductionOut,
    operation_id="update_ad_production",
    responses=api_revision_conflict_responses(404, 422),
    dependencies=[Depends(_validate_cc_multipart_field)],
)
def update_ad_production(
    ad_id: PositivePathId,
    payload: Annotated[AdProductionUpdateForm, Form(media_type="multipart/form-data")],
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
    content_format_provided: bool = Depends(_update_supplies_content_format),
) -> AdProductionOut:
    return AdProductionService(db).update(
        ad_id, payload, actor, content_format_provided=content_format_provided
    )


@router.delete(
    "/{ad_id}",
    response_model=EntityDeleted,
    operation_id="delete_ad_production",
    responses=api_revision_conflict_responses(404, 422),
)
def delete_ad_production(
    ad_id: PositivePathId,
    payload: EntityDelete,
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> EntityDeleted:
    return AdProductionService(db).delete(ad_id, payload, actor)


@router.post(
    "/{ad_id}/withdraw",
    response_model=AdProductionOut,
    operation_id="withdraw_ad_production",
    responses=api_revision_conflict_responses(404, 422),
)
def withdraw_ad_production(
    ad_id: PositivePathId,
    payload: EntityDelete,
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> AdProductionOut:
    return AdProductionService(db).withdraw(ad_id, payload, actor)


@router.patch(
    "/{ad_id}/status",
    response_model=AdProductionOut,
    operation_id="update_ad_production_status",
    responses=api_revision_conflict_responses(404, 422),
)
def update_ad_production_status(
    ad_id: PositivePathId,
    payload: AdProductionStatusChange,
    db: Session = Depends(get_db),
    actor: User = Depends(require_ad_production_view),
) -> AdProductionOut:
    return AdProductionService(db).update_status(ad_id, payload, actor)


def _image_response(
    attachment: tuple[FileObject, BinaryIO], background: BackgroundTasks
) -> StreamingResponse:
    item, stream = attachment
    background.add_task(stream.close)
    return StreamingResponse(
        stream,
        media_type=item.mime_type,
        background=background,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{ad_id}/images/{file_id}",
    response_class=StreamingResponse,
    operation_id="ad_production_image",
    responses=IMAGE_RESPONSES,
)
def get_ad_production_image(
    ad_id: PositivePathId,
    file_id: PositivePathId,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
) -> StreamingResponse:
    return _image_response(AdProductionService(db).open_image(ad_id, file_id, actor), background)


@router.get(
    "/{ad_id}/content-images/{file_id}",
    response_class=StreamingResponse,
    operation_id="ad_production_content_image",
    responses=IMAGE_RESPONSES,
)
def get_ad_production_content_image(
    ad_id: PositivePathId,
    file_id: PositivePathId,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
) -> StreamingResponse:
    return _image_response(
        AdProductionService(db).open_image(ad_id, file_id, actor, inline=True), background
    )

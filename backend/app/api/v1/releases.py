from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.openapi import api_error_responses
from app.core.database import get_db
from app.models.entities import User
from app.schemas.release import OffsetISODatetime, ReleaseOut, ReleasePage
from app.services.release_query_service import ReleaseQueryService

router = APIRouter(prefix="/releases", tags=["releases"])


@router.get(
    "",
    response_model=ReleasePage,
    description=(
        "日期条件只读查询: released_from <= released_at < released_before。"
        "两参数只接受带时区的 ISO datetime, 允许单边; from >= before 或无时区输入返回422。"
        "日期与 version_id、rd.release.view 和 Version DataScope 使用 AND, items/total 一致。"
    ),
)
def list_releases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    version_id: int | None = Query(None),
    released_from: OffsetISODatetime | None = Query(None),
    released_before: OffsetISODatetime | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    if released_from and released_before and released_from >= released_before:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "released_before"),
                    "msg": "发布时间上界必须晚于下界",
                    "input": released_before.isoformat(),
                }
            ]
        )
    return ReleaseQueryService(db).list_for_user(
        current,
        page=page,
        page_size=page_size,
        version_id=version_id,
        released_from=released_from,
        released_before=released_before,
    )


@router.get("/{release_id}", response_model=ReleaseOut, responses=api_error_responses(404))
def get_release(
    release_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_permission("rd.release.view")),
):
    return ReleaseQueryService(db).get_for_user(release_id, current)

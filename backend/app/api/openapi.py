from collections.abc import Mapping
from typing import Any

from app.schemas.common import ErrorResponse, RevisionConflictResponse

_ERROR_DESCRIPTIONS = {
    401: "未登录或登录凭证不可用",
    403: "无权执行该操作",
    404: "资源不存在或不在当前数据范围",
    409: "业务状态或 revision 冲突",
    422: "请求参数或业务数据无效",
}


def api_error_responses(
    *status_codes: int, descriptions: Mapping[int, str] | None = None
) -> dict[int | str, dict[str, Any]]:
    descriptions = descriptions or {}
    return {
        status_code: {
            "model": ErrorResponse,
            "description": descriptions.get(
                status_code, _ERROR_DESCRIPTIONS.get(status_code, "请求失败")
            ),
        }
        for status_code in status_codes
    }


def api_revision_conflict_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    responses = api_error_responses(*status_codes)
    responses[409] = {
        "model": RevisionConflictResponse | ErrorResponse,
        "description": "revision CAS 冲突 (40910) 或该操作的业务冲突",
    }
    return responses

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ensure_all_permissions, require_all_permissions, require_permission
from app.api.openapi import api_revision_conflict_responses
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import Requirement, User
from app.models.enums import Priority, RequirementSource, RequirementStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.requirement import (
    AssigneeOptionsPage,
    LinkedFeedbackOut,
    RequirementCollaboratorGroupUpdate,
    RequirementCollaboratorsOut,
    RequirementCollaboratorsUpdate,
    RequirementCreate,
    RequirementOut,
    RequirementPage,
    RequirementStageStart,
    RequirementStatusChange,
    RequirementUpdate,
)
from app.services.feedback_service import FeedbackService
from app.services.requirement_collaboration_service import RequirementCollaborationService
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/requirements", tags=["requirements"])


def _scoped_requirement_or_404(db: Session, user: User, requirement_id: int) -> Requirement:
    scope = UserRepository(db).data_scope(user.id)
    item = RequirementRepository(db).get_scoped(requirement_id, user.id, scope)
    if item is None:
        raise NotFoundError("需求不存在")
    return item


def _ensure_scoped_version(db: Session, user: User, version_id: int | None) -> None:
    if version_id is None:
        return
    scope = UserRepository(db).data_scope(user.id)
    if VersionRepository(db).get_scoped(version_id, user.id, scope) is None:
        raise NotFoundError("版本不存在")


@router.get(
    "",
    response_model=RequirementPage,
    description=(
        "所有筛选条件与 Requirement DataScope 使用 AND 组合。列表与 total 使用相同条件。"
        "keyword trim 后按编号/标题做大小写不敏感的部分匹配。空白视为无筛选。"
        "current_version_id 与 owner_id 只按需求字段过滤。不要求额外权限或验证关联对象存在。"
    ),
)
def list_requirements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=200),
    status: RequirementStatus | None = Query(None),
    priority: Priority | None = Query(None),
    source: RequirementSource | None = Query(None),
    current_version_id: int | None = Query(None, ge=1),
    owner_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    scope = UserRepository(db).data_scope(user.id)
    items, total = RequirementRepository(db).list_scoped(
        user.id,
        scope,
        page,
        page_size,
        keyword=keyword,
        status=status,
        priority=priority,
        source=source,
        current_version_id=current_version_id,
        owner_id=owner_id,
    )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.post(
    "",
    response_model=RequirementOut,
    responses=api_revision_conflict_responses(409),
    description=(
        "普通创建需要 rd.requirement.create。指定 version_id 与 version_revision 时还需要 "
        "rd.version.edit 和 rd.requirement.view。目标版本同时受 Version DataScope 限制。"
    ),
)
def create_requirement(
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.create")),
):
    if payload.version_id is not None:
        ensure_all_permissions(user, db, "rd.version.edit", "rd.requirement.view")
    scope = UserRepository(db).data_scope(user.id)
    _ensure_scoped_version(db, user, payload.version_id)
    return RequirementService(db).create(payload, user.id, viewer_scope=scope)


@router.get("/assignee-options", response_model=AssigneeOptionsPage)
def assignee_options(
    keyword: str | None = Query(None, max_length=100),
    kind: Literal["OWNER", "DEVELOPER", "DESIGNER"] = "OWNER",
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    return RequirementCollaborationService(db).options(keyword, page, kind)


@router.get("/{requirement_id}/collaborators", response_model=RequirementCollaboratorsOut)
def get_collaborators(
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    item = _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementCollaborationService(db).read(item)


@router.put("/{requirement_id}/collaborators", response_model=RequirementCollaboratorsOut)
def replace_collaborators(
    requirement_id: int,
    payload: RequirementCollaboratorsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementCollaborationService(db).replace(requirement_id, payload, user.id)


@router.get("/{requirement_id}", response_model=RequirementOut)
def get_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.view")),
):
    return _scoped_requirement_or_404(db, user, requirement_id)


@router.post(
    "/{requirement_id}/start-stage",
    response_model=RequirementOut,
    responses=api_revision_conflict_responses(),
)
def start_stage(
    requirement_id: int,
    payload: RequirementStageStart,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.requirement.edit", "rd.requirement.status")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementService(db).start_stage(requirement_id, payload, user.id)


@router.patch(
    "/{requirement_id}/collaborators",
    response_model=RequirementCollaboratorsOut,
    responses=api_revision_conflict_responses(),
)
def update_collaborator_group(
    requirement_id: int,
    payload: RequirementCollaboratorGroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementCollaborationService(db).replace_group(requirement_id, payload, user.id)


@router.get("/{requirement_id}/feedbacks", response_model=list[LinkedFeedbackOut])
def list_requirement_feedbacks(
    requirement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_all_permissions("rd.requirement.view", "rd.feedback.view")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    feedback_scope = UserRepository(db).data_scope(user.id)
    return [
        LinkedFeedbackOut(
            feedback_id=fb.id,
            feedback_no=fb.feedback_no,
            title=fb.title,
            status=fb.status,
            is_primary=is_primary,
        )
        for fb, is_primary in FeedbackService(db).linked_feedbacks(
            requirement_id, viewer_id=user.id, viewer_scope=feedback_scope
        )
    ]


@router.patch(
    "/{requirement_id}",
    response_model=RequirementOut,
    responses=api_revision_conflict_responses(404, 409),
)
def update_requirement(
    requirement_id: int,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.edit")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementService(db).update(requirement_id, payload, user.id)


@router.patch(
    "/{requirement_id}/status",
    response_model=RequirementOut,
    responses=api_revision_conflict_responses(404, 409),
)
def change_status(
    requirement_id: int,
    payload: RequirementStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("rd.requirement.status")),
):
    _scoped_requirement_or_404(db, user, requirement_id)
    return RequirementService(db).change_status(requirement_id, payload, user.id)

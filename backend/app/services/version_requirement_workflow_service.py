from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDenied
from app.models.entities import Requirement, User, Version
from app.models.enums import UserStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository
from app.schemas.entity_actions import BatchActionResponse, BatchActionResult
from app.schemas.version import VersionRequirementSubmitAcceptance
from app.services.revision_conflict import revision_conflict_data
from app.services.workflow_service import WorkflowService


class VersionRequirementWorkflowService:
    """A version-scoped entry into the requirement workflow, one transaction per item."""

    def __init__(self, db: Session):
        self.db = db

    def submit_acceptance(
        self, version_id: int, payload: VersionRequirementSubmitAcceptance, operator_id: int
    ) -> BatchActionResponse:
        results = []
        # HTTP authentication/visibility checks are read-only. End their snapshot so
        # MySQL REPEATABLE READ sees personnel changes completed before these locks.
        self.db.rollback()
        for entry in payload.items:
            try:
                revision = self._submit_one(
                    version_id, payload, entry.id, entry.revision, operator_id
                )
                self.db.commit()
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=True,
                        status_code=200,
                        code=0,
                        message="已提交验收",
                        revision=revision,
                    )
                )
            except AppError as error:
                self.db.rollback()
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=False,
                        status_code=error.status_code,
                        code=error.code,
                        message=error.message,
                        revision=None,
                    )
                )
            except Exception:
                self.db.rollback()
                results.append(
                    BatchActionResult(
                        id=entry.id,
                        success=False,
                        status_code=500,
                        code=50000,
                        message="提交验收失败, 请刷新核对后重试",
                        revision=None,
                    )
                )
        return BatchActionResponse(results=results)

    def _submit_one(
        self,
        version_id: int,
        payload: VersionRequirementSubmitAcceptance,
        requirement_id: int,
        revision: int,
        operator_id: int,
    ) -> int:
        # Use locking reads before any consistent read, including permission/scope
        # queries. A requirement's personnel edits hold the same requirement lock.
        version = self.db.scalar(
            select(Version)
            .where(Version.id == version_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        item = self.db.scalar(
            select(Requirement)
            .where(Requirement.id == requirement_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        user = self.db.get(User, operator_id, populate_existing=True)
        if user is None or user.status != UserStatus.ACTIVE:
            raise PermissionDenied("账号已不可用")
        users = UserRepository(self.db)
        codes = users.permission_codes(operator_id)
        required = {"rd.version.view", "rd.requirement.view", "rd.requirement.status"}
        if "*" not in codes and not required.issubset(codes):
            raise PermissionDenied()
        scope = users.data_scope(operator_id)
        versions = VersionRepository(self.db)
        if version is None or versions.get_scoped(version_id, operator_id, scope) is None:
            raise NotFoundError("版本不存在")
        if (
            item is None
            or RequirementRepository(self.db).get_scoped(requirement_id, operator_id, scope) is None
        ):
            raise NotFoundError("需求不存在")
        if version.status in {"RELEASED", "CANCELED"}:
            raise AppError(40971, "已发布或已取消版本不能提交需求验收", 409)
        if version.revision != payload.version_revision:
            raise ConflictError("版本清单已修改, 请刷新后重试", revision_conflict_data(version))
        if (
            item.current_version_id != version_id
            or versions.active_relation(version_id, requirement_id) is None
        ):
            raise AppError(40971, "需求已不在当前版本清单, 请刷新后重试", 409)
        return WorkflowService(self.db).submit_acceptance_locked(
            item, revision, operator_id, payload.reason
        )

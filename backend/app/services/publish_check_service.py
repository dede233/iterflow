from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.version_progress import effective_version_status, requirement_confirmed
from app.models.entities import Requirement, Version, VersionRequirement
from app.models.enums import DataScope, RequirementStatus, VersionStatus
from app.repositories.requirement_repository import RequirementRepository
from app.repositories.user_repository import UserRepository
from app.repositories.version_repository import VersionRepository

# Requirement statuses that block a publish (anything that is not DONE).
_PUBLISHABLE_REQUIREMENT_STATE = RequirementStatus.DONE


class PublishCheckService:
    """Centralized pre-publish checks (V1.5 Phase 6.2).

    The result is a plain structure (no new tables): {passed, checks[]}. Both
    the preview endpoint (/publish/check) and VersionService.publish() run the
    exact same checks, so a passing check and a passing publish never diverge.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = VersionRepository(db)

    def evaluate(
        self, version: Version, *, lock: bool = False, viewer_id: int | None = None
    ) -> dict:
        checks: list[dict] = []
        if lock:
            active = list(
                self.db.scalars(
                    select(Requirement)
                    .join(VersionRequirement, VersionRequirement.requirement_id == Requirement.id)
                    .where(
                        VersionRequirement.version_id == version.id,
                        VersionRequirement.active.is_(True),
                        Requirement.deleted_at.is_(None),
                    )
                    .order_by(Requirement.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
        else:
            active = self.repo.active_requirements(version.id)
        status = effective_version_status(version.status, active)
        version_ok = status == VersionStatus.READY
        checks.append(
            {
                "type": "VERSION_STATUS_CHECK",
                "passed": version_ok,
                "message": (
                    "关联需求全部完成并确认，可发布"  # noqa: RUF001
                    if version_ok
                    else f"版本进度为 {status}，全部需求完成并确认后才可发布"  # noqa: RUF001
                ),
                "blocking_requirements": [],
            }
        )
        blocking = [
            r
            for r in active
            if RequirementStatus(r.status) != _PUBLISHABLE_REQUIREMENT_STATE
            or not requirement_confirmed(r)
        ]
        visible_blocking = self._visible_blockers(blocking, viewer_id)
        checks.append(
            {
                "type": "REQUIREMENT_STATUS_CHECK",
                "passed": bool(active) and not blocking,
                "message": (
                    "版本尚未关联需求"
                    if not active
                    else "全部需求已完成并确认"
                    if not blocking
                    else "存在未完成或待重新确认的需求, 部分需求无查看权限"
                    if len(visible_blocking) < len(blocking)
                    else f"存在 {len(blocking)} 个未完成或待重新确认的需求"
                ),
                "blocking_requirements": [
                    {"id": r.id, "requirement_no": r.requirement_no, "status": str(r.status)}
                    for r in visible_blocking
                ],
            }
        )

        # Permission is enforced by the endpoint dependency (rd.version.publish);
        # reaching this service means the caller holds it.
        checks.append(
            {
                "type": "PERMISSION_CHECK",
                "passed": True,
                "message": "具备发布权限",
                "blocking_requirements": [],
            }
        )

        return {"passed": all(c["passed"] for c in checks), "checks": checks}

    def _visible_blockers(
        self, blocking: list[Requirement], viewer_id: int | None
    ) -> list[Requirement]:
        if viewer_id is None:
            return blocking
        users = UserRepository(self.db)
        codes = users.permission_codes(viewer_id)
        if "*" not in codes and "rd.requirement.view" not in codes:
            return []
        if users.data_scope(viewer_id) == DataScope.ALL:
            return blocking
        visible = set(
            self.db.scalars(
                select(Requirement.id).where(
                    Requirement.id.in_([r.id for r in blocking]),
                    RequirementRepository.self_criterion(viewer_id),
                )
            )
        )
        return [item for item in blocking if item.id in visible]

    @staticmethod
    def blocking_requirements(result: dict) -> list[dict]:
        blockers = {}
        for check in result["checks"]:
            for requirement in check["blocking_requirements"]:
                blockers[requirement["id"]] = requirement
        return list(blockers.values())

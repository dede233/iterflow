from sqlalchemy.orm import Session

from app.models.entities import Version
from app.models.enums import RequirementStatus, VersionStatus
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

    def evaluate(self, version: Version) -> dict:
        checks: list[dict] = []

        version_ok = VersionStatus(version.status) == VersionStatus.READY
        checks.append(
            {
                "type": "VERSION_STATUS_CHECK",
                "passed": version_ok,
                "message": (
                    "版本处于 READY，可发布"  # noqa: RUF001
                    if version_ok
                    else f"版本状态为 {version.status}，仅 READY 可发布"  # noqa: RUF001
                ),
                "blocking_requirements": [],
            }
        )

        active = self.repo.active_requirements(version.id)
        blocking = [
            r for r in active if RequirementStatus(r.status) != _PUBLISHABLE_REQUIREMENT_STATE
        ]
        checks.append(
            {
                "type": "REQUIREMENT_STATUS_CHECK",
                "passed": not blocking,
                "message": (
                    "全部需求已完成" if not blocking else f"存在 {len(blocking)} 个未完成需求"
                ),
                "blocking_requirements": [
                    {"id": r.id, "requirement_no": r.requirement_no, "status": str(r.status)}
                    for r in blocking
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

    @staticmethod
    def blocking_requirements(result: dict) -> list[dict]:
        for check in result["checks"]:
            if check["type"] == "REQUIREMENT_STATUS_CHECK":
                return check["blocking_requirements"]
        return []

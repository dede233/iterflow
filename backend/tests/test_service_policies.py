from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.entities import Requirement, Version
from app.models.enums import RequirementStatus, VersionStatus
from app.schemas.requirement import RequirementStatusChange
from app.schemas.version import VersionStatusChange
from app.services.requirement_service import RequirementService
from app.services.version_service import VersionService


def test_done_requirement_requires_reason_to_return_to_developing():
    service = RequirementService(MagicMock(spec=Session))
    service.repo = MagicMock()
    service.repo.get.return_value = Requirement(
        id=1,
        status=RequirementStatus.DONE,
        revision=1,
        current_version_id=None,
    )

    with pytest.raises(AppError) as exc_info:
        service.change_status(
            1,
            RequirementStatusChange(status="DEVELOPING", revision=1),
            operator_id=9,
        )

    assert exc_info.value.status_code == 422
    service.repo.update_with_revision.assert_not_called()


def test_requirement_in_released_version_cannot_return_to_developing():
    db = MagicMock(spec=Session)
    db.scalar.return_value = VersionStatus.RELEASED
    service = RequirementService(db)
    service.repo = MagicMock()
    service.repo.get.return_value = Requirement(
        id=1,
        status=RequirementStatus.DONE,
        revision=1,
        current_version_id=7,
    )

    with pytest.raises(AppError) as exc_info:
        service.change_status(
            1,
            RequirementStatusChange(
                status="DEVELOPING",
                revision=1,
                reason="重新开发",
            ),
            operator_id=9,
        )

    assert exc_info.value.status_code == 409
    service.repo.update_with_revision.assert_not_called()


def test_ready_version_requires_reason_to_return_to_testing():
    service = VersionService(MagicMock(spec=Session))
    service.repo = MagicMock()
    service.repo.get.return_value = Version(
        id=1,
        status=VersionStatus.READY,
        revision=1,
    )

    with pytest.raises(AppError) as exc_info:
        service.change_status(
            1,
            VersionStatusChange(status="TESTING", revision=1),
            operator_id=9,
        )

    assert exc_info.value.status_code == 422
    service.repo.update_with_revision.assert_not_called()

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.enums import (
    ManualRequirementStatus,
    ManualVersionStatus,
    RequirementStatus,
    VersionStatus,
)
from app.schemas.requirement import RequirementStatusChange
from app.schemas.version import PublishVersionRequest, VersionStatusChange
from app.services.requirement_service import ALLOWED_TRANSITIONS
from app.services.version_service import VERSION_TRANSITIONS


def test_requirement_happy_path():
    assert ManualRequirementStatus.CONFIRMED in ALLOWED_TRANSITIONS[RequirementStatus.DRAFT]
    assert ManualRequirementStatus.PLANNED in ALLOWED_TRANSITIONS[RequirementStatus.CONFIRMED]
    assert ManualRequirementStatus.DEVELOPING in ALLOWED_TRANSITIONS[RequirementStatus.PLANNED]
    assert ManualRequirementStatus.TESTING in ALLOWED_TRANSITIONS[RequirementStatus.DEVELOPING]
    assert ManualRequirementStatus.DONE in ALLOWED_TRANSITIONS[RequirementStatus.TESTING]


def test_released_version_is_terminal():
    assert VERSION_TRANSITIONS[VersionStatus.RELEASED] == set()


def test_online_cannot_be_requested_through_manual_requirement_status_schema():
    with pytest.raises(ValidationError):
        RequirementStatusChange(status="ONLINE", revision=1)


def test_released_cannot_be_requested_through_manual_version_status_schema():
    with pytest.raises(ValidationError):
        VersionStatusChange(status="RELEASED", revision=1)


def test_ready_can_return_to_testing():
    assert ManualVersionStatus.TESTING in VERSION_TRANSITIONS[VersionStatus.READY]


def test_publish_request_rejects_legacy_result_parameter():
    with pytest.raises(ValidationError):
        PublishVersionRequest(
            released_at=datetime.now(UTC),
            release_notes="release",
            revision=1,
            result="PARTIAL",
        )

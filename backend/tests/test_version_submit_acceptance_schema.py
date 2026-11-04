import pytest
from pydantic import ValidationError

from app.schemas.version import VersionRequirementSubmitAcceptance


@pytest.mark.parametrize(
    "changes",
    [
        {"version_revision": 0},
        {"items": []},
        {"items": [{"id": n, "revision": 1} for n in range(1, 52)]},
        {"items": [{"id": 1, "revision": 1}, {"id": 1, "revision": 2}]},
        {"items": [{"id": 0, "revision": 1}]},
        {"items": [{"id": 1, "revision": 0}]},
        {"reason": "  "},
        {"reason": " a "},
        {"reason": "x" * 501},
    ],
)
def test_version_submit_payload_rejects_invalid_selection_and_reason(changes):
    body = {"version_revision": 1, "items": [{"id": 1, "revision": 1}]}
    with pytest.raises(ValidationError):
        VersionRequirementSubmitAcceptance.model_validate({**body, **changes})


def test_version_submit_reason_is_optional_and_trimmed():
    body = {"version_revision": 1, "items": [{"id": 1, "revision": 1}]}
    assert VersionRequirementSubmitAcceptance.model_validate(body).reason is None
    assert (
        VersionRequirementSubmitAcceptance.model_validate(
            {**body, "reason": "  已实际完成开发  "}
        ).reason
        == "已实际完成开发"
    )

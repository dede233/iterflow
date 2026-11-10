import pytest
from pydantic import ValidationError

from app.schemas.target_release import (
    ReleaseBatchAdjust,
    ReleaseBatchCreate,
    ReleaseTargetComplete,
    ReleaseTargetCreate,
    ReleaseTargetUpdate,
)


@pytest.mark.parametrize("platform", ["PC_WEB", "WECHAT_MINI_PROGRAM", "ALIPAY_MINI_PROGRAM"])
def test_supported_target_platforms(platform):
    assert ReleaseTargetCreate(code="A", name="目标", platform=platform).platform == platform
    assert ReleaseTargetUpdate(revision=1, platform=platform).platform == platform


def test_unknown_platform_is_rejected():
    with pytest.raises(ValidationError):
        ReleaseTargetCreate(code="A", name="目标", platform="UNKNOWN")
    with pytest.raises(ValidationError):
        ReleaseTargetUpdate(revision=1, platform="UNKNOWN")


@pytest.mark.parametrize(
    "bad",
    [
        "javascript:alert(1)",
        "https://name:secret@example.org",
        "https://:secret@example.org",
        "\x00",
    ],
)
def test_target_url_is_inert_and_validated(bad):
    with pytest.raises(ValidationError):
        ReleaseTargetCreate(code="A", name="目标", platform="PC_WEB", url=bad)
    with pytest.raises(ValidationError):
        ReleaseTargetUpdate(revision=1, url=bad)


@pytest.mark.parametrize("ids", [[], [1, 1], [0], list(range(1, 52))])
def test_target_plans_require_distinct_bounded_ids(ids):
    with pytest.raises(ValidationError):
        ReleaseBatchCreate(
            version_revision=1, kind="INITIAL", target_ids=ids, release_notes="本批发布"
        )
    with pytest.raises(ValidationError):
        ReleaseBatchAdjust(version_revision=1, revision=1, target_ids=ids, reason="调整目标")


def test_republish_requires_reason_and_actual_time_needs_offset():
    with pytest.raises(ValidationError):
        ReleaseBatchCreate(
            version_revision=1, kind="REPUBLISH", target_ids=[1], release_notes="重新发布"
        )
    with pytest.raises(ValidationError):
        ReleaseTargetComplete(
            version_revision=1, batch_revision=1, revision=1, released_at="2026-11-09T10:00:00"
        )
    assert ReleaseTargetUpdate(revision=1, url="https://example.org").url == "https://example.org"

"""Historical confirmations retain their instant across database session time zones."""

import runpy
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

utc_iso = runpy.run_path(
    str(Path(__file__).parents[1] / "alembic/versions/0010_requirement_workflow.py")
)["utc_iso"]


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 10, 20, 12, 34, 56),
        datetime(2026, 10, 20, 12, 34, 56, tzinfo=UTC),
        datetime(2026, 10, 20, 20, 34, 56, tzinfo=timezone(timedelta(hours=8))),
        datetime(2026, 10, 20, 7, 34, 56, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_migration_confirmation_preserves_instant(value):
    assert utc_iso(value) == "2026-10-20T12:34:56+00:00"


def test_migration_does_not_invent_confirmation_time():
    assert utc_iso(None) is None

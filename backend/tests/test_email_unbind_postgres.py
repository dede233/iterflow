import pytest
from email_unbind_acceptance import exercise_unbind
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize(
    "scenario", ["account", "off", "pending", "race", "rollback", "delivery", "inflight"]
)
def test_email_unbind_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_unbind(collaboration_pg, scenario, monkeypatch)

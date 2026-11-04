import pytest
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from version_submit_acceptance import SCENARIOS, exercise_version_submit


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_version_submit_acceptance_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_version_submit(collaboration_pg, scenario, monkeypatch)

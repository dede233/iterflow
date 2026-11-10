import pytest
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from target_release_acceptance import SCENARIOS, exercise_targets


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_target_release_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_targets(collaboration_pg, scenario, monkeypatch)

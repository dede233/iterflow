import pytest
from grouped_target_acceptance import GROUP_SCENARIOS, exercise_grouped
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("scenario", GROUP_SCENARIOS)
def test_grouped_targets_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_grouped(collaboration_pg, scenario, monkeypatch)

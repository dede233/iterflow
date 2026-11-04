import pytest
from entity_actions_acceptance import exercise_actions
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize(
    "scenario", ["batch", "rollback", "delete_race", "link_race", "convert_race", "version_race"]
)
def test_entity_actions_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_actions(collaboration_pg, scenario, monkeypatch)

import pytest
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from version_entry_acceptance import exercise_version_entry


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "rollback",
        "unrelated_integrity",
        "duplicate_race",
        "relation_race",
        "delete_race",
    ],
)
def test_version_entry_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_version_entry(collaboration_pg, scenario, monkeypatch)

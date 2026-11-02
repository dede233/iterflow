import pytest
from collaboration_acceptance import exercise_workflow
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize(
    "scenario",
    [
        "bulk",
        "scope",
        "assignment_race",
        "rollback",
        "notification",
        "design",
        "reconfirmation",
        "revocation",
        "return",
        "acceptance",
        "acceptance_multiple",
        "acceptance_race",
        "acceptance_migration",
    ],
)
def test_workflow_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_workflow(collaboration_pg, scenario, monkeypatch)

import pytest
from collaboration_acceptance import exercise_workflow
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize(
    "scenario",
    [
        "scope",
        "assignment_race",
        "rollback",
        "notification",
        "design",
        "reconfirmation",
        "revocation",
        "return",
        "acceptance",
    ],
)
def test_workflow_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_workflow(collaboration_pg, scenario, monkeypatch)

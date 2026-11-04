import pytest
from issue4_workflow_acceptance import exercise_issue4
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize(
    "scenario",
    ["race", "migration_plain", "migration_format", "migration_deleted", "migration_multiple"],
)
def test_issue4_workflow_postgres(collaboration_pg, scenario):
    exercise_issue4(collaboration_pg, scenario)

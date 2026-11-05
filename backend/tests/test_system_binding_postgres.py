import pytest
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from system_binding_acceptance import exercise_binding


@pytest.mark.parametrize("scenario", ["cross_system", "race", "migration"])
def test_system_binding_postgres(collaboration_pg, scenario):
    exercise_binding(collaboration_pg, scenario)

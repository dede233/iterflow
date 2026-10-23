import pytest
from test_collaboration_postgres import collaboration_pg as collaboration_pg
from version_role_acceptance import exercise_version_role


@pytest.mark.parametrize("role_code", ["DEVELOPER", "PRODUCT_MANAGER", "DEVELOPMENT_LEAD"])
def test_version_role_workflow_postgres(collaboration_pg, role_code, monkeypatch):
    exercise_version_role(collaboration_pg, role_code, monkeypatch)

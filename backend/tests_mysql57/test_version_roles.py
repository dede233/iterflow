import pytest
from test_acceptance import mysql_api as mysql_api
from version_role_acceptance import exercise_version_role


@pytest.mark.parametrize("role_code", ["DEVELOPER", "PRODUCT_MANAGER", "DEVELOPMENT_LEAD"])
def test_version_role_workflow_mysql(mysql_api, role_code, monkeypatch):
    exercise_version_role(mysql_api, role_code, monkeypatch)

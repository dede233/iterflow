import pytest
from issue4_workflow_acceptance import exercise_issue4
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize(
    "scenario",
    ["race", "migration_plain", "migration_format", "migration_deleted", "migration_multiple"],
)
def test_issue4_workflow_mysql(mysql_api, scenario):
    exercise_issue4(mysql_api, scenario)

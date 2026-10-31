import pytest
from collaboration_acceptance import exercise_workflow
from test_acceptance import mysql_api as mysql_api


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
    ],
)
def test_workflow_mysql(mysql_api, scenario, monkeypatch):
    exercise_workflow(mysql_api, scenario, monkeypatch)

import pytest
from test_acceptance import mysql_api as mysql_api
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
def test_version_entry_mysql(mysql_api, scenario, monkeypatch):
    exercise_version_entry(mysql_api, scenario, monkeypatch)

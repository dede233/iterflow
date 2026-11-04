import pytest
from entity_actions_acceptance import exercise_actions
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize(
    "scenario", ["batch", "rollback", "delete_race", "link_race", "convert_race", "version_race"]
)
def test_entity_actions_mysql(mysql_api, scenario, monkeypatch):
    exercise_actions(mysql_api, scenario, monkeypatch)

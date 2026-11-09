import pytest
from target_release_acceptance import SCENARIOS, exercise_targets
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_target_release_mysql(mysql_api, scenario, monkeypatch):
    exercise_targets(mysql_api, scenario, monkeypatch)

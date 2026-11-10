import pytest
from grouped_target_acceptance import GROUP_SCENARIOS, exercise_grouped
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", GROUP_SCENARIOS)
def test_grouped_targets_mysql(mysql_api, scenario, monkeypatch):
    exercise_grouped(mysql_api, scenario, monkeypatch)

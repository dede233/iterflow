import pytest
from test_acceptance import mysql_api as mysql_api
from version_submit_acceptance import SCENARIOS, exercise_version_submit


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_version_submit_acceptance_mysql(mysql_api, scenario, monkeypatch):
    exercise_version_submit(mysql_api, scenario, monkeypatch)

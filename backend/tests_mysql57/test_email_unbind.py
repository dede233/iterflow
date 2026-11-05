import pytest
from email_unbind_acceptance import exercise_unbind
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize(
    "scenario", ["account", "off", "pending", "race", "rollback", "delivery", "inflight"]
)
def test_email_unbind_mysql(mysql_api, scenario, monkeypatch):
    exercise_unbind(mysql_api, scenario, monkeypatch)

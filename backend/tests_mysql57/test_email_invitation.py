import pytest
from email_invitation_acceptance import exercise_email_invitation
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", ["automatic", "legacy"])
def test_email_invitation_mysql(mysql_api, scenario, monkeypatch):
    exercise_email_invitation(mysql_api, scenario, monkeypatch)

import pytest
from mail_notice_acceptance import exercise_notice
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", ["account", "migration"])
def test_mail_notice_mysql(mysql_api, scenario):
    exercise_notice(mysql_api, scenario)

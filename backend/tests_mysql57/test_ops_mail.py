import pytest
from ops_mail_acceptance import exercise_ops_mail
from test_acceptance import mysql_api as mysql_api
from test_mail_delivery_postgres import smtp_sink as smtp_sink


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ops_mail_mysql(mysql_api, kind, smtp_sink, monkeypatch):
    exercise_ops_mail(mysql_api, kind, smtp_sink, monkeypatch)

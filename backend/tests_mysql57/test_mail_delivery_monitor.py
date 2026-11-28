from mail_delivery_monitor_acceptance import (
    exercise_failed_collaboration_mail_resend,
    exercise_mail_delivery_monitor,
    exercise_mail_delivery_resend,
)
from test_acceptance import mysql_api as mysql_api


def test_mail_delivery_monitor_mysql(mysql_api, monkeypatch):
    exercise_mail_delivery_monitor(mysql_api, monkeypatch)


def test_mail_delivery_resend_mysql(mysql_api, monkeypatch):
    exercise_mail_delivery_resend(mysql_api, monkeypatch)


def test_failed_collaboration_mail_resend_mysql(mysql_api, monkeypatch):
    exercise_failed_collaboration_mail_resend(mysql_api, monkeypatch)

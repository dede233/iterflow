from mail_delivery_monitor_acceptance import (
    exercise_failed_collaboration_mail_resend,
    exercise_mail_delivery_monitor,
    exercise_mail_delivery_resend,
)
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


def test_mail_delivery_monitor_postgres(collaboration_pg, monkeypatch):
    exercise_mail_delivery_monitor(collaboration_pg, monkeypatch)


def test_mail_delivery_resend_postgres(collaboration_pg, monkeypatch):
    exercise_mail_delivery_resend(collaboration_pg, monkeypatch)


def test_failed_collaboration_mail_resend_postgres(collaboration_pg, monkeypatch):
    exercise_failed_collaboration_mail_resend(collaboration_pg, monkeypatch)

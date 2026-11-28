import pytest
from ops_mail_acceptance import exercise_ops_mail
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from test_mail_delivery_postgres import smtp_sink as smtp_sink


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ops_mail_postgres(collaboration_pg, kind, smtp_sink, monkeypatch):
    exercise_ops_mail(collaboration_pg, kind, smtp_sink, monkeypatch)

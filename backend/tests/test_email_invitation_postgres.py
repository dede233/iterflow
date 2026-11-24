import pytest
from email_invitation_acceptance import exercise_email_invitation
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("scenario", ["automatic", "legacy"])
def test_email_invitation_postgres(collaboration_pg, scenario, monkeypatch):
    exercise_email_invitation(collaboration_pg, scenario, monkeypatch)

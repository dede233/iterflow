import pytest
from mail_notice_acceptance import exercise_notice
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("scenario", ["account", "migration"])
def test_mail_notice_postgres(collaboration_pg, scenario):
    exercise_notice(collaboration_pg, scenario)

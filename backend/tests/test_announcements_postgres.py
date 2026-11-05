import pytest
from announcement_acceptance import exercise_announcements
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("scenario", ["lifecycle", "race"])
def test_announcements_postgres(collaboration_pg, scenario):
    exercise_announcements(collaboration_pg, scenario)


def test_announcement_migration_postgres(collaboration_pg):
    from announcement_acceptance import exercise_announcement_migration

    exercise_announcement_migration(collaboration_pg)

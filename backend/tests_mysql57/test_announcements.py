import pytest
from announcement_acceptance import exercise_announcements
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", ["lifecycle", "race"])
def test_announcements_mysql(mysql_api, scenario):
    exercise_announcements(mysql_api, scenario)


def test_announcement_migration_mysql(mysql_api):
    from announcement_acceptance import exercise_announcement_migration

    exercise_announcement_migration(mysql_api)

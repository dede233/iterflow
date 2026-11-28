from soft_deletion_migration_acceptance import exercise_soft_deletion_migration
from test_acceptance import mysql_api as mysql_api


def test_soft_deletion_migration_mysql57(mysql_api):
    exercise_soft_deletion_migration(mysql_api)

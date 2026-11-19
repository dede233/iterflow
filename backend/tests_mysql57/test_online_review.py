from online_review_acceptance import exercise_online_review, exercise_online_review_migration
from test_acceptance import mysql_api as mysql_api


def test_online_review_mysql(mysql_api):
    exercise_online_review(mysql_api)


def test_online_review_migration_mysql(mysql_api):
    exercise_online_review_migration(mysql_api)

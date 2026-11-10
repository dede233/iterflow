from entity_activity_acceptance import exercise_entity_activity
from test_acceptance import mysql_api as mysql_api


def test_entity_activity_mysql(mysql_api):
    exercise_entity_activity(mysql_api)

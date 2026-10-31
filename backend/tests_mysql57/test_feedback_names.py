from feedback_reference_acceptance import exercise_feedback_reference_names
from test_acceptance import mysql_api as mysql_api


def test_feedback_reference_names_mysql(mysql_api):
    exercise_feedback_reference_names(mysql_api)

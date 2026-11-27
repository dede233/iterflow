from feedback_ad_rich_text_acceptance import exercise_feedback_ad_rich_text
from test_acceptance import mysql_api as mysql_api


def test_feedback_ad_rich_text_mysql57(mysql_api):
    exercise_feedback_ad_rich_text(mysql_api)

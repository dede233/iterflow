from filter_options_acceptance import exercise_filter_options
from test_acceptance import mysql_api as mysql_api


def test_scoped_filter_options_mysql(mysql_api):
    exercise_filter_options(mysql_api)

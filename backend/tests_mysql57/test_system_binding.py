import pytest
from system_binding_acceptance import exercise_binding
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("scenario", ["cross_system", "race", "migration"])
def test_system_binding_mysql(mysql_api, scenario):
    exercise_binding(mysql_api, scenario)

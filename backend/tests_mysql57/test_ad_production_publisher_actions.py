import pytest
from ad_production_publisher_actions_acceptance import exercise_ad_production_publisher_actions
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ad_production_publisher_actions_mysql57(mysql_api, kind):
    exercise_ad_production_publisher_actions(mysql_api, kind)

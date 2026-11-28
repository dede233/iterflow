import pytest
from ad_production_cc_acceptance import (
    exercise_ad_production_cc,
    exercise_ad_production_cc_migration,
)
from test_acceptance import mysql_api as mysql_api


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ad_production_cc_mysql57(mysql_api, kind):
    exercise_ad_production_cc(mysql_api, kind)


def test_ad_production_cc_migration_mysql57(mysql_api):
    exercise_ad_production_cc_migration(mysql_api)

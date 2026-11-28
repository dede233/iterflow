from ad_production_kinds_acceptance import (
    exercise_ad_production_creator_correction,
    exercise_ad_production_default_roles,
    exercise_ad_production_kind_permissions,
    exercise_ad_production_kinds,
    exercise_ad_production_kinds_concurrency,
    exercise_ad_production_kinds_migration,
)
from test_acceptance import mysql_api as mysql_api


def test_ad_production_default_roles_mysql57(mysql_api):
    exercise_ad_production_default_roles(mysql_api)


def test_ad_production_kinds_mysql57(mysql_api):
    exercise_ad_production_kinds(mysql_api)


def test_ad_production_kinds_concurrency_mysql57(mysql_api):
    exercise_ad_production_kinds_concurrency(mysql_api)


def test_ad_production_kind_permissions_mysql57(mysql_api):
    exercise_ad_production_kind_permissions(mysql_api)


def test_ad_production_kinds_migration_mysql57(mysql_api):
    exercise_ad_production_kinds_migration(mysql_api)


def test_ad_production_creator_correction_mysql57(mysql_api):
    exercise_ad_production_creator_correction(mysql_api)

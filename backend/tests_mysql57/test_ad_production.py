from ad_production_acceptance import (
    exercise_ad_production,
    exercise_ad_production_people,
    exercise_ad_production_people_migration,
    exercise_ad_production_publication,
    exercise_ad_production_publication_migration,
    exercise_ad_production_role_upgrade,
    exercise_material_production_names_migration,
)
from test_acceptance import mysql_api as mysql_api


def test_ad_production_mysql57(mysql_api):
    exercise_ad_production(mysql_api)


def test_ad_production_people_mysql57(mysql_api):
    exercise_ad_production_people(mysql_api)


def test_ad_production_people_migration_mysql57(mysql_api):
    exercise_ad_production_people_migration(mysql_api)


def test_ad_production_role_upgrade_mysql57(mysql_api):
    exercise_ad_production_role_upgrade(mysql_api)


def test_ad_production_publication_mysql57(mysql_api):
    exercise_ad_production_publication(mysql_api)


def test_ad_production_publication_migration_mysql57(mysql_api):
    exercise_ad_production_publication_migration(mysql_api)


def test_material_production_names_migration_mysql57(mysql_api):
    exercise_material_production_names_migration(mysql_api)

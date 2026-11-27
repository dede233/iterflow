import pytest
from ops_production_permissions_acceptance import (
    exercise_ops_default_guards,
    exercise_ops_default_migration,
    exercise_ops_defaults_fresh_seed,
    exercise_ops_production_permission_guards,
    exercise_ops_production_permission_migration,
)
from test_acceptance import mysql_api as mysql_api


def test_ops_production_permission_migration_mysql57(mysql_api):
    exercise_ops_production_permission_migration(mysql_api)


def test_ops_production_permission_guards_mysql57(mysql_api):
    exercise_ops_production_permission_guards(mysql_api)


def test_ops_preset_migration_mysql57(mysql_api, monkeypatch):
    exercise_ops_default_migration(mysql_api, monkeypatch)


def test_ops_preset_migration_skips_ineligible_roles_mysql57(mysql_api):
    exercise_ops_default_guards(mysql_api)


@pytest.mark.parametrize("mysql_api", ["fresh"], indirect=True)
def test_ops_preset_fresh_seed_mysql57(mysql_api):
    exercise_ops_defaults_fresh_seed(mysql_api)

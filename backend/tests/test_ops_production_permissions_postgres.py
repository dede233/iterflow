import pytest
from ops_production_permissions_acceptance import (
    exercise_ops_default_guards,
    exercise_ops_default_migration,
    exercise_ops_defaults_fresh_seed,
    exercise_ops_production_permission_guards,
    exercise_ops_production_permission_migration,
)
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


def test_ops_production_permission_migration_postgres(collaboration_pg):
    exercise_ops_production_permission_migration(collaboration_pg)


def test_ops_production_permission_guards_postgres(collaboration_pg):
    exercise_ops_production_permission_guards(collaboration_pg)


def test_ops_preset_migration_postgres(collaboration_pg, monkeypatch):
    exercise_ops_default_migration(collaboration_pg, monkeypatch)


def test_ops_preset_migration_skips_ineligible_roles_postgres(collaboration_pg):
    exercise_ops_default_guards(collaboration_pg)


@pytest.mark.parametrize("collaboration_pg", ["fresh"], indirect=True)
def test_ops_preset_fresh_seed_postgres(collaboration_pg):
    exercise_ops_defaults_fresh_seed(collaboration_pg)

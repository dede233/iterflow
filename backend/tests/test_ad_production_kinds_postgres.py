from ad_production_kinds_acceptance import (
    exercise_ad_production_creator_correction,
    exercise_ad_production_default_roles,
    exercise_ad_production_kind_permissions,
    exercise_ad_production_kinds,
    exercise_ad_production_kinds_concurrency,
    exercise_ad_production_kinds_migration,
)
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


def test_ad_production_default_roles_postgres(collaboration_pg):
    exercise_ad_production_default_roles(collaboration_pg)


def test_ad_production_kinds_postgres(collaboration_pg):
    exercise_ad_production_kinds(collaboration_pg)


def test_ad_production_kinds_concurrency_postgres(collaboration_pg):
    exercise_ad_production_kinds_concurrency(collaboration_pg)


def test_ad_production_kind_permissions_postgres(collaboration_pg):
    exercise_ad_production_kind_permissions(collaboration_pg)


def test_ad_production_kinds_migration_postgres(collaboration_pg):
    exercise_ad_production_kinds_migration(collaboration_pg)


def test_ad_production_creator_correction_postgres(collaboration_pg):
    exercise_ad_production_creator_correction(collaboration_pg)

from ad_production_acceptance import (
    exercise_ad_production,
    exercise_ad_production_people,
    exercise_ad_production_people_migration,
    exercise_ad_production_publication,
    exercise_ad_production_publication_migration,
    exercise_ad_production_role_upgrade,
    exercise_material_production_names_migration,
)
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


def test_ad_production_postgres(collaboration_pg):
    exercise_ad_production(collaboration_pg)


def test_ad_production_people_postgres(collaboration_pg):
    exercise_ad_production_people(collaboration_pg)


def test_ad_production_people_migration_postgres(collaboration_pg):
    exercise_ad_production_people_migration(collaboration_pg)


def test_ad_production_role_upgrade_postgres(collaboration_pg):
    exercise_ad_production_role_upgrade(collaboration_pg)


def test_ad_production_publication_postgres(collaboration_pg):
    exercise_ad_production_publication(collaboration_pg)


def test_ad_production_publication_migration_postgres(collaboration_pg):
    exercise_ad_production_publication_migration(collaboration_pg)


def test_material_production_names_migration_postgres(collaboration_pg):
    exercise_material_production_names_migration(collaboration_pg)

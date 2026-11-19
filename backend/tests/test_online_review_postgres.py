from online_review_acceptance import exercise_online_review, exercise_online_review_migration
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


def test_online_review_postgres(collaboration_pg):
    exercise_online_review(collaboration_pg)


def test_online_review_migration_postgres(collaboration_pg):
    exercise_online_review_migration(collaboration_pg)

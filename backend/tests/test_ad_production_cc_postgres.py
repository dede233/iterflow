import pytest
from ad_production_cc_acceptance import (
    exercise_ad_production_cc,
    exercise_ad_production_cc_migration,
)
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ad_production_cc_postgres(collaboration_pg, kind):
    exercise_ad_production_cc(collaboration_pg, kind)


def test_ad_production_cc_migration_postgres(collaboration_pg):
    exercise_ad_production_cc_migration(collaboration_pg)

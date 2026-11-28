import pytest
from ad_production_publisher_actions_acceptance import exercise_ad_production_publisher_actions
from seeded_postgres_fixture import collaboration_pg as collaboration_pg


@pytest.mark.parametrize("kind", ["MATERIAL", "MERCHANT_AD"])
def test_ad_production_publisher_actions_postgres(collaboration_pg, kind):
    exercise_ad_production_publisher_actions(collaboration_pg, kind)

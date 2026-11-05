import pytest
from seeded_postgres_fixture import collaboration_pg as collaboration_pg
from version_progress_acceptance import exercise_version_progress


@pytest.mark.parametrize(
    "scenario",
    [
        "projection",
        "publish_race",
        "content_publish_race",
        "roster_publish_race",
        "cancel_publish_race",
    ],
)
def test_version_progress_postgres(collaboration_pg, scenario):
    exercise_version_progress(collaboration_pg, scenario)

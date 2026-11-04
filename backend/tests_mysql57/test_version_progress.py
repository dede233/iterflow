import pytest
from test_acceptance import mysql_api as mysql_api
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
def test_version_progress_mysql(mysql_api, scenario):
    exercise_version_progress(mysql_api, scenario)

from app.services.requirement_service import ALLOWED_TRANSITIONS
from app.services.version_service import VERSION_TRANSITIONS


def test_requirement_happy_path():
    assert "CONFIRMED" in ALLOWED_TRANSITIONS["DRAFT"]
    assert "PLANNED" in ALLOWED_TRANSITIONS["CONFIRMED"]
    assert "DEVELOPING" in ALLOWED_TRANSITIONS["PLANNED"]
    assert "TESTING" in ALLOWED_TRANSITIONS["DEVELOPING"]
    assert "DONE" in ALLOWED_TRANSITIONS["TESTING"]
    assert "ONLINE" in ALLOWED_TRANSITIONS["DONE"]


def test_released_version_is_terminal():
    assert VERSION_TRANSITIONS["RELEASED"] == set()

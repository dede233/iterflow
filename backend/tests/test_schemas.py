import pytest
from pydantic import ValidationError

from app.models.entities import Feedback, Notification, Release, Requirement, Role, User, Version
from app.models.enums import (
    DataScope,
    FeedbackType,
    FeedbackUrgency,
    NotificationType,
    Priority,
    UserStatus,
)
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate
from app.schemas.role import RoleCreate, RoleOut, RoleUpdate
from app.schemas.user import UserOut


def test_feedback_create_validates_business_enums():
    payload = FeedbackCreate(
        title="反馈标题",
        feedback_type=FeedbackType.SYSTEM_ISSUE,
        urgency=FeedbackUrgency.URGENT,
        description="反馈内容",
    )
    assert payload.feedback_type is FeedbackType.SYSTEM_ISSUE

    with pytest.raises(ValidationError):
        FeedbackCreate(
            title="反馈标题",
            feedback_type="TYPO",
            description="反馈内容",
        )


def test_feedback_patch_requires_only_revision():
    payload = FeedbackUpdate(revision=3)
    assert payload.model_dump(exclude_unset=True) == {"revision": 3}

    with pytest.raises(ValidationError):
        FeedbackUpdate(title=None, revision=3)


def test_priority_and_data_scope_are_strongly_validated():
    assert Priority.P2.value == "P2"
    assert RoleCreate(code="DEV", name="开发").data_scope is DataScope.SELF
    with pytest.raises(ValidationError):
        RoleCreate(code="DEV", name="开发", data_scope="ORGANIZATION")
    with pytest.raises(ValidationError):
        RoleCreate(code="DEV", name="开发", data_scope=DataScope.TEAM)
    with pytest.raises(ValidationError):
        RoleUpdate(data_scope=DataScope.TEAM, revision=1)


def test_role_database_default_is_self_and_team_remains_reserved_enum():
    assert Role.__table__.c.data_scope.default.arg is DataScope.SELF
    assert DataScope.TEAM.value == "TEAM"


def test_role_response_exposes_revision_required_by_write_apis():
    response = RoleOut.model_validate(
        Role(
            id=7,
            code="MEMBER",
            name="普通成员",
            data_scope=DataScope.SELF,
            enabled=True,
            is_system=False,
            revision=3,
        )
    )

    assert response.revision == 3


def test_user_response_never_contains_password_hash():
    user = User(
        id=1,
        username="alice",
        display_name="Alice",
        password_hash="secret-hash",
        email=None,
        status=UserStatus.ACTIVE,
        revision=1,
    )

    serialized = UserOut.model_validate(user).model_dump()

    assert "password_hash" not in serialized


def test_business_enum_columns_validate_strings_before_database_write():
    enum_columns = (
        User.__table__.c.status,
        Feedback.__table__.c.feedback_type,
        Feedback.__table__.c.urgency,
        Feedback.__table__.c.status,
        Requirement.__table__.c.source,
        Requirement.__table__.c.priority,
        Requirement.__table__.c.status,
        Version.__table__.c.status,
        Release.__table__.c.result,
        Notification.__table__.c.type,
    )

    assert all(column.type.validate_strings for column in enum_columns)
    assert NotificationType.RELEASE.value == "RELEASE"

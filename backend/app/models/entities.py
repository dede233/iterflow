from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import (
    DataScope,
    FeedbackStatus,
    FeedbackType,
    FeedbackUrgency,
    NotificationType,
    Priority,
    ReleaseResult,
    RequirementSource,
    RequirementStatus,
    StorageDriver,
    UserStatus,
    VersionStatus,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class User(Base, AuditMixin):
    __tablename__ = "sys_user"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    mobile: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(
            UserStatus,
            name="user_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=UserStatus.ACTIVE,
        index=True,
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(Base, AuditMixin):
    __tablename__ = "sys_role"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    data_scope: Mapped[DataScope] = mapped_column(
        SAEnum(
            DataScope,
            name="data_scope",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=DataScope.SELF,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Permission(Base):
    __tablename__ = "sys_permission"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(32), default="BUTTON")


class UserRole(Base):
    __tablename__ = "sys_user_role"
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), primary_key=True)


class RefreshSession(Base):
    """A server-side refresh-token session.

    Raw refresh tokens are deliberately never persisted.  The signed refresh
    JWT contains the session id (``sid``) and the one-time token identifier
    (``jti``); both must match this record before a token can be refreshed.
    """

    __tablename__ = "sys_refresh_session"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.id", ondelete="CASCADE"), index=True
    )
    token_jti: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(64))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RolePermission(Base):
    __tablename__ = "sys_role_permission"
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_role.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_permission.id"), primary_key=True
    )


class BusinessSystem(Base, AuditMixin):
    __tablename__ = "sys_business_system"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class BusinessModule(Base, AuditMixin):
    __tablename__ = "sys_business_module"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_business_system.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("system_id", "code", name="uq_module_system_code"),)


class Dictionary(Base, AuditMixin):
    __tablename__ = "sys_dictionary"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DictionaryItem(Base, AuditMixin):
    __tablename__ = "sys_dictionary_item"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dictionary_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_dictionary.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (
        UniqueConstraint("dictionary_id", "code", name="uq_dictionary_item_dictionary_code"),
    )


class Requirement(Base, AuditMixin):
    __tablename__ = "rd_requirement"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requirement_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    requirement_type: Mapped[str] = mapped_column(String(32))
    source: Mapped[RequirementSource] = mapped_column(
        SAEnum(
            RequirementSource,
            name="requirement_source",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=RequirementSource.DIRECT,
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(
            Priority,
            name="priority",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=Priority.P2,
        index=True,
    )
    status: Mapped[RequirementStatus] = mapped_column(
        SAEnum(
            RequirementStatus,
            name="requirement_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=RequirementStatus.DRAFT,
        index=True,
    )
    system_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_business_system.id"))
    module_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_business_module.id"))
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"), index=True)
    current_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("rd_version.id", use_alter=True, name="fk_requirement_current_version"),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)


class Feedback(Base, AuditMixin):
    __tablename__ = "rd_feedback"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    feedback_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    feedback_type: Mapped[FeedbackType] = mapped_column(
        SAEnum(
            FeedbackType,
            name="feedback_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        )
    )
    urgency: Mapped[FeedbackUrgency] = mapped_column(
        SAEnum(
            FeedbackUrgency,
            name="feedback_urgency",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=FeedbackUrgency.NORMAL,
    )
    status: Mapped[FeedbackStatus] = mapped_column(
        SAEnum(
            FeedbackStatus,
            name="feedback_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=FeedbackStatus.NEW,
        index=True,
    )
    system_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_business_system.id"))
    module_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_business_module.id"))
    submitter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    actual_result: Mapped[str | None] = mapped_column(Text)
    reproduce_steps: Mapped[str | None] = mapped_column(Text)
    main_requirement_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("rd_requirement.id"), index=True
    )
    duplicate_of_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("rd_feedback.id"))


class Version(Base, AuditMixin):
    __tablename__ = "rd_version"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[VersionStatus] = mapped_column(
        SAEnum(
            VersionStatus,
            name="version_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=VersionStatus.PLANNING,
        index=True,
    )
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    planned_release_date: Mapped[date | None] = mapped_column(Date)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)


class RequirementFeedback(Base):
    __tablename__ = "rd_requirement_feedback"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rd_requirement.id", ondelete="CASCADE"), index=True
    )
    feedback_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rd_feedback.id", ondelete="CASCADE"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VersionRequirement(Base):
    __tablename__ = "rd_version_requirement"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rd_version.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rd_requirement.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    added_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_user.id"))
    removed_reason: Mapped[str | None] = mapped_column(String(500))


class Release(Base, AuditMixin):
    __tablename__ = "rd_release"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("rd_version.id"), index=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[ReleaseResult] = mapped_column(
        SAEnum(
            ReleaseResult,
            name="release_result",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=ReleaseResult.SUCCESS,
    )
    release_notes: Mapped[str] = mapped_column(Text)
    rollback_notes: Mapped[str | None] = mapped_column(Text)


class Notification(Base, AuditMixin):
    __tablename__ = "sys_notification"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=NotificationType.SYSTEM,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class FileObject(Base, AuditMixin):
    __tablename__ = "sys_file"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_driver: Mapped[StorageDriver] = mapped_column(
        SAEnum(
            StorageDriver,
            name="storage_driver",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )


class AttachmentRelation(Base):
    __tablename__ = "sys_attachment_relation"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_file.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comment(Base, AuditMixin):
    __tablename__ = "rd_comment"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, index=True)
    content: Mapped[str] = mapped_column(Text)


class OperationLog(Base):
    __tablename__ = "sys_operation_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    operator_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.id"), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    before_data: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    after_data: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


Index("ix_feedback_system_module", Feedback.system_id, Feedback.module_id)
Index("ix_requirement_system_module", Requirement.system_id, Requirement.module_id)

"""Create the IterFlow V1.5 initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> tuple[sa.Column[object], ...]:
    """Return the common auditable-entity columns used by ``AuditMixin``."""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "sys_user",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "DISABLED",
                "LOCKED",
                name="user_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_user_status", "sys_user", ["status"], unique=False)
    op.create_index("ix_sys_user_username", "sys_user", ["username"], unique=True)

    op.create_table(
        "sys_role",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "data_scope",
            sa.Enum(
                "SELF",
                "TEAM",
                "ALL",
                name="data_scope",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="SELF",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "sys_permission",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_permission_code", "sys_permission", ["code"], unique=True)

    op.create_table(
        "sys_business_system",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "sys_dictionary",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_dictionary_code", "sys_dictionary", ["code"], unique=True)

    op.create_table(
        "sys_dictionary_item",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("dictionary_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["dictionary_id"], ["sys_dictionary.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dictionary_id", "code", name="uq_dictionary_item_dictionary_code"
        ),
    )
    op.create_index(
        "ix_sys_dictionary_item_dictionary_id",
        "sys_dictionary_item",
        ["dictionary_id"],
        unique=False,
    )

    op.create_table(
        "sys_user_role",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"]),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    op.create_table(
        "sys_role_permission",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["sys_permission.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["sys_role.id"]),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "sys_business_module",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("system_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["system_id"], ["sys_business_system.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_id", "code", name="uq_module_system_code"),
    )
    op.create_index(
        "ix_sys_business_module_system_id",
        "sys_business_module",
        ["system_id"],
        unique=False,
    )

    op.create_table(
        "rd_version",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PLANNING",
                "DEVELOPING",
                "TESTING",
                "READY",
                "RELEASED",
                "CANCELED",
                name="version_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("planned_release_date", sa.Date(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["owner_id"], ["sys_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rd_version_status", "rd_version", ["status"], unique=False)
    op.create_index("ix_rd_version_version_no", "rd_version", ["version_no"], unique=True)

    op.create_table(
        "rd_requirement",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_no", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "DIRECT",
                "FEEDBACK",
                name="requirement_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "P0",
                "P1",
                "P2",
                "P3",
                "P4",
                name="priority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "CONFIRMED",
                "PLANNED",
                "DEVELOPING",
                "TESTING",
                "DONE",
                "ONLINE",
                "PAUSED",
                "CANCELED",
                name="requirement_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("system_id", sa.BigInteger(), nullable=True),
        sa.Column("module_id", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["module_id"], ["sys_business_module.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["sys_user.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["sys_business_system.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "fk_requirement_current_version",
        "rd_requirement",
        "rd_version",
        ["current_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_rd_requirement_current_version_id",
        "rd_requirement",
        ["current_version_id"],
        unique=False,
    )
    op.create_index("ix_rd_requirement_owner_id", "rd_requirement", ["owner_id"], unique=False)
    op.create_index("ix_rd_requirement_priority", "rd_requirement", ["priority"], unique=False)
    op.create_index(
        "ix_rd_requirement_requirement_no",
        "rd_requirement",
        ["requirement_no"],
        unique=True,
    )
    op.create_index("ix_rd_requirement_status", "rd_requirement", ["status"], unique=False)
    op.create_index(
        "ix_requirement_system_module",
        "rd_requirement",
        ["system_id", "module_id"],
        unique=False,
    )

    op.create_table(
        "rd_feedback",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("feedback_no", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "feedback_type",
            sa.Enum(
                "NEW_FEATURE",
                "FEATURE_OPTIMIZATION",
                "SYSTEM_ISSUE",
                "DATA_ISSUE",
                "UI_UX",
                "OTHER",
                name="feedback_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "urgency",
            sa.Enum(
                "NORMAL",
                "URGENT",
                "CRITICAL",
                name="feedback_urgency",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "ACCEPTED",
                "REQUIREMENT_LINKED",
                "PLANNED",
                "DEVELOPING",
                "TESTING",
                "ONLINE",
                "DUPLICATE",
                "CANNOT_REPRODUCE",
                "CLOSED",
                name="feedback_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("system_id", sa.BigInteger(), nullable=True),
        sa.Column("module_id", sa.BigInteger(), nullable=True),
        sa.Column("submitter_id", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("reproduce_steps", sa.Text(), nullable=True),
        sa.Column("main_requirement_id", sa.BigInteger(), nullable=True),
        sa.Column("duplicate_of_id", sa.BigInteger(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["rd_feedback.id"]),
        sa.ForeignKeyConstraint(["main_requirement_id"], ["rd_requirement.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["sys_business_module.id"]),
        sa.ForeignKeyConstraint(["submitter_id"], ["sys_user.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["sys_business_system.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rd_feedback_feedback_no", "rd_feedback", ["feedback_no"], unique=True)
    op.create_index(
        "ix_rd_feedback_main_requirement_id",
        "rd_feedback",
        ["main_requirement_id"],
        unique=False,
    )
    op.create_index("ix_rd_feedback_status", "rd_feedback", ["status"], unique=False)
    op.create_index("ix_rd_feedback_submitter_id", "rd_feedback", ["submitter_id"], unique=False)
    op.create_index(
        "ix_feedback_system_module",
        "rd_feedback",
        ["system_id", "module_id"],
        unique=False,
    )

    op.create_table(
        "rd_requirement_feedback",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("feedback_id", sa.BigInteger(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feedback_id"], ["rd_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["rd_requirement.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rd_requirement_feedback_feedback_id",
        "rd_requirement_feedback",
        ["feedback_id"],
        unique=False,
    )
    op.create_index(
        "ix_rd_requirement_feedback_requirement_id",
        "rd_requirement_feedback",
        ["requirement_id"],
        unique=False,
    )
    op.create_index(
        "uq_feedback_primary_relation",
        "rd_requirement_feedback",
        ["feedback_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "rd_version_requirement",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("requirement_id", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by", sa.BigInteger(), nullable=True),
        sa.Column("removed_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["added_by"], ["sys_user.id"]),
        sa.ForeignKeyConstraint(["removed_by"], ["sys_user.id"]),
        sa.ForeignKeyConstraint(["requirement_id"], ["rd_requirement.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["rd_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rd_version_requirement_active",
        "rd_version_requirement",
        ["active"],
        unique=False,
    )
    op.create_index(
        "ix_rd_version_requirement_requirement_id",
        "rd_version_requirement",
        ["requirement_id"],
        unique=False,
    )
    op.create_index(
        "ix_rd_version_requirement_version_id",
        "rd_version_requirement",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        "uq_requirement_active_version",
        "rd_version_requirement",
        ["requirement_id"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "rd_release",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "result",
            sa.Enum(
                "SUCCESS",
                name="release_result",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("release_notes", sa.Text(), nullable=False),
        sa.Column("rollback_notes", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["version_id"], ["rd_version.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rd_release_version_id", "rd_release", ["version_id"], unique=False)

    op.create_table(
        "sys_notification",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "SYSTEM",
                "FEEDBACK",
                "REQUIREMENT",
                "VERSION",
                "RELEASE",
                name="notification_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
            server_default="SYSTEM",
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_notification_read_at", "sys_notification", ["read_at"], unique=False)
    op.create_index("ix_sys_notification_type", "sys_notification", ["type"], unique=False)
    op.create_index("ix_sys_notification_user_id", "sys_notification", ["user_id"], unique=False)

    op.create_table(
        "sys_file",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "storage_driver",
            sa.Enum(
                "LOCAL",
                "S3",
                name="storage_driver",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_sys_file_sha256", "sys_file", ["sha256"], unique=False)

    op.create_table(
        "sys_attachment_relation",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["sys_file.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sys_attachment_relation_entity_id",
        "sys_attachment_relation",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_sys_attachment_relation_entity_type",
        "sys_attachment_relation",
        ["entity_type"],
        unique=False,
    )

    op.create_table(
        "rd_comment",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rd_comment_entity_id", "rd_comment", ["entity_id"], unique=False)
    op.create_index("ix_rd_comment_entity_type", "rd_comment", ["entity_type"], unique=False)

    op.create_table(
        "sys_operation_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["operator_id"], ["sys_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sys_operation_log_action", "sys_operation_log", ["action"], unique=False)
    op.create_index(
        "ix_sys_operation_log_created_at",
        "sys_operation_log",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sys_operation_log_entity_id",
        "sys_operation_log",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_sys_operation_log_entity_type",
        "sys_operation_log",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        "ix_sys_operation_log_operator_id",
        "sys_operation_log",
        ["operator_id"],
        unique=False,
    )
    op.create_index(
        "ix_sys_operation_log_request_id",
        "sys_operation_log",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("sys_operation_log")
    op.drop_table("rd_comment")
    op.drop_table("sys_attachment_relation")
    op.drop_table("sys_file")
    op.drop_table("sys_notification")
    op.drop_table("rd_release")
    op.drop_table("rd_version_requirement")
    op.drop_table("rd_requirement_feedback")
    op.drop_table("rd_feedback")
    op.drop_constraint("fk_requirement_current_version", "rd_requirement", type_="foreignkey")
    op.drop_table("rd_requirement")
    op.drop_table("rd_version")
    op.drop_table("sys_business_module")
    op.drop_table("sys_dictionary_item")
    op.drop_table("sys_dictionary")
    op.drop_table("sys_role_permission")
    op.drop_table("sys_user_role")
    op.drop_table("sys_business_system")
    op.drop_table("sys_permission")
    op.drop_table("sys_role")
    op.drop_table("sys_user")

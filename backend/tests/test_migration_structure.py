import ast
from pathlib import Path

MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial.py"
REFRESH_SESSION_MIGRATION_PATH = (
    Path(__file__).parents[1] / "alembic" / "versions" / "0002_refresh_sessions.py"
)
ROLE_SYSTEM_FLAG_MIGRATION_PATH = (
    Path(__file__).parents[1] / "alembic" / "versions" / "0003_role_system_flag.py"
)
EXPECTED_TABLES = {
    "rd_comment",
    "rd_feedback",
    "rd_release",
    "rd_requirement",
    "rd_requirement_feedback",
    "rd_version",
    "rd_version_requirement",
    "sys_attachment_relation",
    "sys_business_module",
    "sys_business_system",
    "sys_dictionary",
    "sys_dictionary_item",
    "sys_file",
    "sys_notification",
    "sys_operation_log",
    "sys_permission",
    "sys_role",
    "sys_role_permission",
    "sys_user",
    "sys_user_role",
}
EXPECTED_INDEXES = {
    "ix_feedback_system_module",
    "ix_rd_comment_entity_id",
    "ix_rd_comment_entity_type",
    "ix_rd_feedback_feedback_no",
    "ix_rd_feedback_main_requirement_id",
    "ix_rd_feedback_status",
    "ix_rd_feedback_submitter_id",
    "ix_rd_release_version_id",
    "ix_rd_requirement_current_version_id",
    "ix_rd_requirement_feedback_feedback_id",
    "ix_rd_requirement_feedback_requirement_id",
    "ix_rd_requirement_owner_id",
    "ix_rd_requirement_priority",
    "ix_rd_requirement_requirement_no",
    "ix_rd_requirement_status",
    "ix_rd_version_requirement_active",
    "ix_rd_version_requirement_requirement_id",
    "ix_rd_version_requirement_version_id",
    "ix_rd_version_status",
    "ix_rd_version_version_no",
    "ix_requirement_system_module",
    "ix_sys_attachment_relation_entity_id",
    "ix_sys_attachment_relation_entity_type",
    "ix_sys_business_module_system_id",
    "ix_sys_dictionary_code",
    "ix_sys_dictionary_item_dictionary_id",
    "ix_sys_file_sha256",
    "ix_sys_notification_read_at",
    "ix_sys_notification_type",
    "ix_sys_notification_user_id",
    "ix_sys_operation_log_action",
    "ix_sys_operation_log_created_at",
    "ix_sys_operation_log_entity_id",
    "ix_sys_operation_log_entity_type",
    "ix_sys_operation_log_operator_id",
    "ix_sys_operation_log_request_id",
    "ix_sys_permission_code",
    "ix_sys_user_status",
    "ix_sys_user_username",
    "uq_feedback_primary_relation",
    "uq_requirement_active_version",
}
EXPECTED_DROP_ORDER = [
    "sys_operation_log",
    "rd_comment",
    "sys_attachment_relation",
    "sys_file",
    "sys_notification",
    "rd_release",
    "rd_version_requirement",
    "rd_requirement_feedback",
    "rd_feedback",
    "rd_requirement",
    "rd_version",
    "sys_business_module",
    "sys_dictionary_item",
    "sys_dictionary",
    "sys_role_permission",
    "sys_user_role",
    "sys_business_system",
    "sys_permission",
    "sys_role",
    "sys_user",
]


def _operation_first_arguments(operation: str) -> list[str]:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    arguments: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != operation or not node.args:
            continue
        first_argument = node.args[0]
        if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
            arguments.append(first_argument.value)
    return arguments


def _operation_count(operation: str) -> int:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == operation
    )


def test_initial_migration_uses_explicit_operations() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "Base.metadata" not in source
    assert ".create_all(" not in source
    assert ".drop_all(" not in source
    assert set(_operation_first_arguments("create_table")) == EXPECTED_TABLES
    assert _operation_first_arguments("drop_table") == EXPECTED_DROP_ORDER
    assert set(_operation_first_arguments("create_index")) == EXPECTED_INDEXES
    assert _operation_first_arguments("create_foreign_key") == ["fk_requirement_current_version"]
    assert _operation_count("ForeignKeyConstraint") == 25


def test_initial_migration_uses_postgresql_jsonb_for_audit_payloads() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'sa.Column("before_data", postgresql.JSONB' in source
    assert 'sa.Column("after_data", postgresql.JSONB' in source
    assert 'sa.Column("user_agent", sa.String(length=512)' in source


def test_initial_migration_has_business_partial_unique_indexes() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert '"uq_feedback_primary_relation"' in source
    assert 'postgresql_where=sa.text("is_primary = true")' in source
    assert '"uq_requirement_active_version"' in source
    assert 'postgresql_where=sa.text("active = true")' in source


def test_refresh_session_migration_is_explicit_and_reversible() -> None:
    source = REFRESH_SESSION_MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "0001_initial"' in source
    assert 'op.create_table(\n        "sys_refresh_session"' in source
    assert 'sa.Column("token_jti", sa.String(length=32), nullable=False)' in source
    assert 'sa.UniqueConstraint("token_jti")' in source
    assert 'op.create_index(\n        "ix_sys_refresh_session_user_id"' in source
    assert 'op.create_index(\n        "ix_sys_refresh_session_expires_at"' in source
    assert 'op.drop_table("sys_refresh_session")' in source
    assert "Base.metadata" not in source


def test_role_system_flag_migration_is_explicit_and_reversible() -> None:
    source = ROLE_SYSTEM_FLAG_MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "0002_refresh_sessions"' in source
    assert 'op.add_column(\n        "sys_role"' in source
    assert (
        'sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false())' in source
    )
    assert "UPDATE sys_role SET is_system = true" in source
    assert 'op.drop_column("sys_role", "is_system")' in source
    assert "Base.metadata" not in source

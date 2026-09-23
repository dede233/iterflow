"""Enforce V1 relationship integrity at the database boundary.

Revision ID: 0004_integrity_contract_hardening
Revises: 0003_role_system_flag
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_integrity"
down_revision: str | None = "0003_role_system_flag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fail_if_rows_exist(description: str, query: str) -> None:
    if op.get_bind().scalar(sa.text(query)):
        raise RuntimeError(
            f"Cannot apply 0004_integrity_contract_hardening: {description}. "
            "Resolve the data integrity issue explicitly before upgrading."
        )


def _validate_existing_data() -> None:
    _fail_if_rows_exist(
        "duplicate Release rows exist for a Version",
        """
        SELECT EXISTS (
            SELECT 1 FROM rd_release GROUP BY version_id HAVING count(*) > 1
        )
        """,
    )
    _fail_if_rows_exist(
        "duplicate AttachmentRelation entity/file tuples exist",
        """
        SELECT EXISTS (
            SELECT 1 FROM sys_attachment_relation
            GROUP BY entity_type, entity_id, file_id HAVING count(*) > 1
        )
        """,
    )
    _fail_if_rows_exist(
        "duplicate RequirementFeedback pairs exist",
        """
        SELECT EXISTS (
            SELECT 1 FROM rd_requirement_feedback
            GROUP BY requirement_id, feedback_id HAVING count(*) > 1
        )
        """,
    )
    _fail_if_rows_exist(
        "Requirement.current_version_id disagrees with its active VersionRequirement",
        """
        SELECT EXISTS (
            SELECT 1
            FROM rd_requirement AS r
            LEFT JOIN LATERAL (
                SELECT count(*) AS active_count,
                       count(*) FILTER (WHERE vr.version_id = r.current_version_id)
                           AS matching_count
                FROM rd_version_requirement AS vr
                WHERE vr.requirement_id = r.id AND vr.active
            ) AS relation_state ON true
            WHERE (r.current_version_id IS NULL AND relation_state.active_count <> 0)
               OR (r.current_version_id IS NOT NULL
                   AND (relation_state.active_count <> 1 OR relation_state.matching_count <> 1))
        )
        """,
    )
    _fail_if_rows_exist(
        "Feedback.main_requirement_id disagrees with its PRIMARY RequirementFeedback",
        """
        SELECT EXISTS (
            SELECT 1
            FROM rd_feedback AS f
            LEFT JOIN LATERAL (
                SELECT count(*) FILTER (WHERE rf.is_primary) AS primary_count,
                       count(*) FILTER (
                           WHERE rf.is_primary AND rf.requirement_id = f.main_requirement_id
                       ) AS matching_count
                FROM rd_requirement_feedback AS rf
                WHERE rf.feedback_id = f.id
            ) AS relation_state ON true
            WHERE (f.main_requirement_id IS NULL AND relation_state.primary_count <> 0)
               OR (f.main_requirement_id IS NOT NULL
                   AND (relation_state.primary_count <> 1 OR relation_state.matching_count <> 1))
        )
        """,
    )


def _create_consistency_functions() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_assert_requirement_version_consistency(p_requirement_id bigint)
            RETURNS void LANGUAGE plpgsql AS $$
            DECLARE
                current_id bigint;
                active_count bigint;
                matching_count bigint;
            BEGIN
                SELECT current_version_id INTO current_id
                FROM rd_requirement WHERE id = p_requirement_id;
                IF NOT FOUND THEN
                    RETURN;
                END IF;

                SELECT count(*), count(*) FILTER (WHERE version_id = current_id)
                INTO active_count, matching_count
                FROM rd_version_requirement
                WHERE requirement_id = p_requirement_id AND active;

                IF (current_id IS NULL AND active_count <> 0)
                   OR (current_id IS NOT NULL AND (active_count <> 1 OR matching_count <> 1)) THEN
                    RAISE EXCEPTION
                        'Requirement % has an inconsistent active version relation',
                        p_requirement_id
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_requirement_current_version_relation';
                END IF;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_assert_feedback_primary_consistency(p_feedback_id bigint)
            RETURNS void LANGUAGE plpgsql AS $$
            DECLARE
                main_id bigint;
                primary_count bigint;
                matching_count bigint;
            BEGIN
                SELECT main_requirement_id INTO main_id
                FROM rd_feedback WHERE id = p_feedback_id;
                IF NOT FOUND THEN
                    RETURN;
                END IF;

                SELECT count(*) FILTER (WHERE is_primary),
                       count(*) FILTER (WHERE is_primary AND requirement_id = main_id)
                INTO primary_count, matching_count
                FROM rd_requirement_feedback
                WHERE feedback_id = p_feedback_id;

                IF (main_id IS NULL AND primary_count <> 0)
                   OR (main_id IS NOT NULL AND (primary_count <> 1 OR matching_count <> 1)) THEN
                    RAISE EXCEPTION
                        'Feedback % has an inconsistent primary requirement relation',
                        p_feedback_id
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_feedback_main_requirement_relation';
                END IF;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_check_requirement_version_trigger()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM iterflow_assert_requirement_version_consistency(NEW.id);
                RETURN NULL;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_check_version_requirement_trigger()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    PERFORM iterflow_assert_requirement_version_consistency(OLD.requirement_id);
                ELSIF TG_OP = 'UPDATE' THEN
                    PERFORM iterflow_assert_requirement_version_consistency(OLD.requirement_id);
                    IF NEW.requirement_id IS DISTINCT FROM OLD.requirement_id THEN
                        PERFORM iterflow_assert_requirement_version_consistency(NEW.requirement_id);
                    END IF;
                ELSIF TG_OP = 'INSERT' THEN
                    PERFORM iterflow_assert_requirement_version_consistency(NEW.requirement_id);
                END IF;
                RETURN NULL;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_check_feedback_main_trigger()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM iterflow_assert_feedback_primary_consistency(NEW.id);
                RETURN NULL;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION iterflow_check_requirement_feedback_trigger()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    PERFORM iterflow_assert_feedback_primary_consistency(OLD.feedback_id);
                ELSIF TG_OP = 'UPDATE' THEN
                    PERFORM iterflow_assert_feedback_primary_consistency(OLD.feedback_id);
                    IF NEW.feedback_id IS DISTINCT FROM OLD.feedback_id THEN
                        PERFORM iterflow_assert_feedback_primary_consistency(NEW.feedback_id);
                    END IF;
                ELSIF TG_OP = 'INSERT' THEN
                    PERFORM iterflow_assert_feedback_primary_consistency(NEW.feedback_id);
                END IF;
                RETURN NULL;
            END;
            $$;
            """
        )
    )


def _create_constraint_triggers() -> None:
    op.execute(
        sa.text(
            """
            CREATE CONSTRAINT TRIGGER ct_requirement_current_version_consistency
            AFTER INSERT OR UPDATE ON rd_requirement
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION iterflow_check_requirement_version_trigger();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE CONSTRAINT TRIGGER ct_version_requirement_consistency
            AFTER INSERT OR UPDATE OR DELETE ON rd_version_requirement
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION iterflow_check_version_requirement_trigger();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE CONSTRAINT TRIGGER ct_feedback_main_requirement_consistency
            AFTER INSERT OR UPDATE ON rd_feedback
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION iterflow_check_feedback_main_trigger();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE CONSTRAINT TRIGGER ct_requirement_feedback_consistency
            AFTER INSERT OR UPDATE OR DELETE ON rd_requirement_feedback
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION iterflow_check_requirement_feedback_trigger();
            """
        )
    )


def upgrade() -> None:
    _validate_existing_data()

    op.drop_index("ix_rd_release_version_id", table_name="rd_release")
    op.create_unique_constraint("uq_release_version_id", "rd_release", ["version_id"])

    op.drop_index("ix_sys_attachment_relation_entity_id", table_name="sys_attachment_relation")
    op.drop_index("ix_sys_attachment_relation_entity_type", table_name="sys_attachment_relation")
    op.create_unique_constraint(
        "uq_attachment_entity_file",
        "sys_attachment_relation",
        ["entity_type", "entity_id", "file_id"],
    )
    op.create_index(
        "ix_attachment_entity_type_entity_id",
        "sys_attachment_relation",
        ["entity_type", "entity_id"],
    )
    op.create_index("ix_attachment_file_id", "sys_attachment_relation", ["file_id"])

    op.create_unique_constraint(
        "uq_requirement_feedback_pair",
        "rd_requirement_feedback",
        ["requirement_id", "feedback_id"],
    )

    _create_consistency_functions()
    _create_constraint_triggers()


def downgrade() -> None:
    for trigger_name, table_name in (
        ("ct_requirement_current_version_consistency", "rd_requirement"),
        ("ct_version_requirement_consistency", "rd_version_requirement"),
        ("ct_feedback_main_requirement_consistency", "rd_feedback"),
        ("ct_requirement_feedback_consistency", "rd_requirement_feedback"),
    ):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))

    for function_name in (
        "iterflow_check_requirement_version_trigger",
        "iterflow_check_version_requirement_trigger",
        "iterflow_check_feedback_main_trigger",
        "iterflow_check_requirement_feedback_trigger",
    ):
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {function_name}() CASCADE"))

    # The two assertion helpers accept a bigint argument.
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS iterflow_assert_requirement_version_consistency(bigint)")
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS iterflow_assert_feedback_primary_consistency(bigint)")
    )

    op.drop_constraint("uq_requirement_feedback_pair", "rd_requirement_feedback", type_="unique")

    op.drop_index("ix_attachment_file_id", table_name="sys_attachment_relation")
    op.drop_index("ix_attachment_entity_type_entity_id", table_name="sys_attachment_relation")
    op.drop_constraint("uq_attachment_entity_file", "sys_attachment_relation", type_="unique")
    op.create_index(
        "ix_sys_attachment_relation_entity_id",
        "sys_attachment_relation",
        ["entity_id"],
    )
    op.create_index(
        "ix_sys_attachment_relation_entity_type",
        "sys_attachment_relation",
        ["entity_type"],
    )

    op.drop_constraint("uq_release_version_id", "rd_release", type_="unique")
    op.create_index("ix_rd_release_version_id", "rd_release", ["version_id"])

"""Track feedback and advertising editor formats without rewriting old content."""

import sqlalchemy as sa

FORMATS = (("rd_feedback", "description_format"), ("ops_ad_production", "content_format"))


def upgrade(op):
    for table, column in FORMATS:
        op.add_column(
            table, sa.Column(column, sa.String(8), nullable=False, server_default="PLAIN")
        )


def downgrade(op):
    connection = op.get_bind()
    for table, column in FORMATS:
        if connection.scalar(sa.text(f"SELECT 1 FROM {table} WHERE {column} <> 'PLAIN' LIMIT 1")):
            raise RuntimeError("Feedback or ad production rich text exists; downgrade refused")
    if connection.scalar(
        sa.text(
            "SELECT 1 FROM sys_attachment_relation "
            "WHERE entity_type IN ('FEEDBACK_IMAGE', 'AD_PRODUCTION_IMAGE') LIMIT 1"
        )
    ):
        raise RuntimeError("Inline editor image history exists; downgrade refused")
    for table, column in reversed(FORMATS):
        op.drop_column(table, column)

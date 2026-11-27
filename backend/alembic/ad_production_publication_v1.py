"""Add advertising titles and deadlines while retaining legacy records."""

import sqlalchemy as sa

TABLE = "ops_ad_production"
PUBLICATION_INDEX = "ix_ad_production_created_at_id"


def upgrade(op):
    if op.get_bind().dialect.name == "mysql":
        # Use one statement because MySQL commits each ALTER TABLE implicitly.
        op.execute(
            f"ALTER TABLE {TABLE} "
            "ADD COLUMN title VARCHAR(200) NULL, "
            "ADD COLUMN due_at DATETIME(6) NULL, "
            f"ADD INDEX {PUBLICATION_INDEX} (created_at, id)"
        )
    else:
        op.add_column(TABLE, sa.Column("title", sa.String(200), nullable=True))
        op.add_column(TABLE, sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(PUBLICATION_INDEX, TABLE, ["created_at", "id"])


def downgrade(op):
    connection = op.get_bind()
    is_mysql = connection.dialect.name == "mysql"
    if not is_mysql:
        op.execute(f"LOCK TABLE {TABLE} IN ACCESS EXCLUSIVE MODE")
    has_publication_data = connection.scalar(
        sa.text(f"SELECT 1 FROM {TABLE} WHERE title IS NOT NULL OR due_at IS NOT NULL LIMIT 1")
    )
    if has_publication_data:
        raise RuntimeError("Ad production downgrade refused because titles or deadlines exist")

    if is_mysql:
        op.execute(
            f"ALTER TABLE {TABLE} DROP INDEX {PUBLICATION_INDEX}, "
            "DROP COLUMN due_at, DROP COLUMN title"
        )
    else:
        op.drop_index(PUBLICATION_INDEX, table_name=TABLE)
        op.drop_column(TABLE, "due_at")
        op.drop_column(TABLE, "title")

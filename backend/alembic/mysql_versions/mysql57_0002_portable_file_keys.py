"""Exact long file keys under the 767-byte limit; upgrade legacy local 0001 too."""

import runpy
from pathlib import Path

from sqlalchemy import inspect, text

from alembic import op

revision = "mysql57_0002"
down_revision = "mysql57_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("MySQL migration requires MySQL")
    file_keys = runpy.run_path(str(Path(__file__).parents[1] / "mysql_file_keys.py"))
    columns = {column["name"] for column in inspect(bind).get_columns("sys_file")}
    if "storage_key_leaf_id" in columns:
        # Fresh OFF baseline already installed every constraint before inserting files.
        return
    file_keys["create_registry"](bind)
    bind.execute(text("ALTER TABLE sys_file ADD storage_key_leaf_id BIGINT NULL DEFAULT 1"))
    bind.execute(
        text("UPDATE sys_file SET storage_key_leaf_id=iterflow_register_file_key(storage_key)")
    )
    unique = [
        index["name"]
        for index in inspect(bind).get_indexes("sys_file")
        if index["unique"] and index["column_names"] == ["storage_key"]
    ]
    if len(unique) != 1:
        raise RuntimeError("Legacy file storage key uniqueness missing; inspect partial DDL")
    old_index = bind.dialect.identifier_preparer.quote(unique[0])
    # One ALTER swaps constraints. Never expose a populated file table without uniqueness.
    bind.execute(
        text(
            "ALTER TABLE sys_file MODIFY storage_key_leaf_id BIGINT NOT NULL DEFAULT 1, "
            "MODIFY storage_key VARBINARY(2004) NOT NULL, "
            "ADD CONSTRAINT uq_sys_file_storage_key_leaf UNIQUE (storage_key_leaf_id), "
            "ADD CONSTRAINT fk_sys_file_storage_key_leaf FOREIGN KEY (storage_key_leaf_id) "
            "REFERENCES iterflow_file_key_node(id) ON DELETE RESTRICT, "
            f"DROP INDEX {old_index}"
        )
    )
    for statement in file_keys["FILE_TRIGGERS"]:
        bind.execute(text(statement))


def downgrade():
    raise RuntimeError("Portable file key protection cannot be removed by downgrade")

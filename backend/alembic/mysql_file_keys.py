"""Frozen MySQL 0001/0002 DDL: exact long-key uniqueness with 512-byte edges.

This is a physical index structure, not an application entity or a hash index.
Do not change this migration helper after publication; add a new revision.
"""

from sqlalchemy import text

TABLE = "iterflow_file_key_node"
FUNCTION = "iterflow_register_file_key"
COLUMN = "storage_key_leaf_id"
INDEX = "uq_sys_file_storage_key_leaf"
FK = "fk_sys_file_storage_key_leaf"

CREATE_TABLE = """
CREATE TABLE iterflow_file_key_node (
  id BIGINT NOT NULL AUTO_INCREMENT,
  parent_id BIGINT NOT NULL,
  segment VARBINARY(512) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT uq_file_key_edge UNIQUE (parent_id, segment),
  CONSTRAINT fk_file_key_parent FOREIGN KEY (parent_id)
    REFERENCES iterflow_file_key_node(id) ON DELETE RESTRICT
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC CHARSET=utf8mb4 COLLATE utf8mb4_bin
"""

CREATE_FUNCTION = """
CREATE FUNCTION iterflow_register_file_key(key_bytes VARBINARY(2000))
RETURNS BIGINT NOT DETERMINISTIC MODIFIES SQL DATA SQL SECURITY DEFINER
BEGIN
  DECLARE parent BIGINT DEFAULT 1;
  DECLARE previous_parent BIGINT;
  DECLARE position_bytes INT DEFAULT 1;
  DECLARE edge VARBINARY(512);
  IF key_bytes IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid null storage key';
  END IF;
  WHILE position_bytes <= OCTET_LENGTH(key_bytes) DO
    SET edge = SUBSTRING(key_bytes, position_bytes, 512);
    SET previous_parent = parent;
    INSERT INTO iterflow_file_key_node(parent_id, segment)
      VALUES(previous_parent, edge) ON DUPLICATE KEY UPDATE id=id;
    SELECT id INTO parent FROM iterflow_file_key_node
      WHERE parent_id=previous_parent AND segment=edge FOR UPDATE;
    SET position_bytes = position_bytes + 512;
  END WHILE;
  RETURN parent;
END
"""

NODE_TRIGGERS = [
    """CREATE TRIGGER domain_iterflow_file_key_node_insert
    BEFORE INSERT ON iterflow_file_key_node FOR EACH ROW BEGIN
      IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key integrity checks disabled';
      END IF;
      IF NEW.parent_id < 1 OR OCTET_LENGTH(NEW.segment)=0 OR NEW.id=NEW.parent_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid file key edge';
      END IF;
    END""",
    """CREATE TRIGGER domain_iterflow_file_key_node_update
    BEFORE UPDATE ON iterflow_file_key_node FOR EACH ROW BEGIN
      IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key integrity checks disabled';
      END IF;
      IF NOT (NEW.id <=> OLD.id) OR NOT (NEW.parent_id <=> OLD.parent_id)
          OR NOT (NEW.segment <=> OLD.segment) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key edges are immutable';
      END IF;
    END""",
    """CREATE TRIGGER domain_iterflow_file_key_node_delete
    BEFORE DELETE ON iterflow_file_key_node FOR EACH ROW BEGIN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key edges are immutable';
    END""",
]

FILE_TRIGGERS = [
    """CREATE TRIGGER storage_key_sys_file_insert BEFORE INSERT ON sys_file FOR EACH ROW
    FOLLOWS domain_sys_file_insert BEGIN
      IF NOT (NEW.storage_key_leaf_id <=> 1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key leaf is database managed';
      END IF;
      SET NEW.storage_key_leaf_id=iterflow_register_file_key(NEW.storage_key);
    END""",
    """CREATE TRIGGER storage_key_sys_file_update BEFORE UPDATE ON sys_file FOR EACH ROW
    FOLLOWS domain_sys_file_update BEGIN
      IF NOT (NEW.storage_key_leaf_id <=> OLD.storage_key_leaf_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='file key leaf is database managed';
      END IF;
      IF NOT (NEW.storage_key <=> OLD.storage_key) THEN
        SET NEW.storage_key_leaf_id=iterflow_register_file_key(NEW.storage_key);
      END IF;
    END""",
]


def create_registry(bind):
    bind.execute(text(CREATE_TABLE))
    # Root represents the empty key, which was legal at the original DB level.
    bind.execute(text("INSERT INTO iterflow_file_key_node VALUES (1,1,X'')"))
    for statement in NODE_TRIGGERS:
        bind.execute(text(statement))
    bind.execute(text(CREATE_FUNCTION))


def portable_file_ddl(statement):
    return statement.replace(
        "\tstorage_key VARBINARY(2000) NOT NULL,",
        # Overflow space lets the 500-character guard reject permissive truncation.
        "\tstorage_key VARBINARY(2004) NOT NULL,\n\tstorage_key_leaf_id BIGINT NOT NULL DEFAULT 1,",
    ).replace(
        "UNIQUE (storage_key)",
        "CONSTRAINT uq_sys_file_storage_key_leaf UNIQUE (storage_key_leaf_id),\n"
        "\tCONSTRAINT fk_sys_file_storage_key_leaf FOREIGN KEY (storage_key_leaf_id) "
        "REFERENCES iterflow_file_key_node(id) ON DELETE RESTRICT",
    )

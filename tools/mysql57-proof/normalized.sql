-- Single authoritative relationship representation: no redundant writable pointers.
CREATE TABLE rd_version (id BIGINT PRIMARY KEY) ENGINE=InnoDB;
CREATE TABLE rd_requirement (id BIGINT PRIMARY KEY, revision INT NOT NULL) ENGINE=InnoDB;
CREATE TABLE rd_feedback (id BIGINT PRIMARY KEY, revision INT NOT NULL) ENGINE=InnoDB;
CREATE TABLE rd_requirement_feedback (
 id BIGINT PRIMARY KEY, requirement_id BIGINT NOT NULL, feedback_id BIGINT NOT NULL,
 is_primary TINYINT NOT NULL,
 primary_feedback_id BIGINT GENERATED ALWAYS AS (IF(is_primary=1,feedback_id,NULL)) STORED,
 UNIQUE KEY uq_primary (primary_feedback_id), UNIQUE KEY uq_pair (requirement_id,feedback_id),
 FOREIGN KEY (requirement_id) REFERENCES rd_requirement(id),
 FOREIGN KEY (feedback_id) REFERENCES rd_feedback(id)
) ENGINE=InnoDB;
CREATE TABLE rd_version_requirement (
 id BIGINT PRIMARY KEY, requirement_id BIGINT NOT NULL, version_id BIGINT NOT NULL,
 active TINYINT NOT NULL,
 active_requirement_id BIGINT GENERATED ALWAYS AS (IF(active=1,requirement_id,NULL)) STORED,
 UNIQUE KEY uq_active (active_requirement_id),
 FOREIGN KEY (requirement_id) REFERENCES rd_requirement(id),
 FOREIGN KEY (version_id) REFERENCES rd_version(id)
) ENGINE=InnoDB;
CREATE VIEW rd_requirement_read AS
 SELECT r.*, (SELECT vr.version_id FROM rd_version_requirement vr WHERE vr.requirement_id=r.id AND vr.active=1) AS current_version_id FROM rd_requirement r;
CREATE VIEW rd_feedback_read AS
 SELECT f.*, (SELECT rf.requirement_id FROM rd_requirement_feedback rf WHERE rf.feedback_id=f.id AND rf.is_primary=1) AS main_requirement_id FROM rd_feedback f;
DELIMITER $$
CREATE TRIGGER vr_domain_insert BEFORE INSERT ON rd_version_requirement FOR EACH ROW
BEGIN IF NEW.active NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid active'; END IF; END$$
CREATE TRIGGER vr_domain_update BEFORE UPDATE ON rd_version_requirement FOR EACH ROW
BEGIN IF NEW.active NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid active'; END IF; END$$
CREATE TRIGGER rf_domain_insert BEFORE INSERT ON rd_requirement_feedback FOR EACH ROW
BEGIN IF NEW.is_primary NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid primary'; END IF; END$$
CREATE TRIGGER rf_domain_update BEFORE UPDATE ON rd_requirement_feedback FOR EACH ROW
BEGIN IF NEW.is_primary NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid primary'; END IF; END$$
DELIMITER ;

DELIMITER $$
CREATE TRIGGER settings_rd_version_insert BEFORE INSERT ON rd_version FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_version_update BEFORE UPDATE ON rd_version FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_version_delete BEFORE DELETE ON rd_version FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_insert BEFORE INSERT ON rd_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_update BEFORE UPDATE ON rd_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_delete BEFORE DELETE ON rd_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_feedback_insert BEFORE INSERT ON rd_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_feedback_update BEFORE UPDATE ON rd_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_feedback_delete BEFORE DELETE ON rd_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_feedback_insert BEFORE INSERT ON rd_requirement_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_feedback_update BEFORE UPDATE ON rd_requirement_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_requirement_feedback_delete BEFORE DELETE ON rd_requirement_feedback FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_version_requirement_insert BEFORE INSERT ON rd_version_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_version_requirement_update BEFORE UPDATE ON rd_version_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
CREATE TRIGGER settings_rd_version_requirement_delete BEFORE DELETE ON rd_version_requirement FOR EACH ROW
BEGIN IF @@foreign_key_checks <> 1 OR @@unique_checks <> 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='integrity checks must remain enabled'; END IF; END$$
DELIMITER ;

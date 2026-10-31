-- Disposable phase-0 model only. Not an application migration.
CREATE TABLE rd_version (id BIGINT PRIMARY KEY) ENGINE=InnoDB;
CREATE TABLE rd_requirement (
 id BIGINT PRIMARY KEY, current_version_id BIGINT NULL, revision INT NOT NULL DEFAULT 1,
 FOREIGN KEY (current_version_id) REFERENCES rd_version(id)
) ENGINE=InnoDB;
CREATE TABLE rd_feedback (
 id BIGINT PRIMARY KEY, main_requirement_id BIGINT NULL, revision INT NOT NULL DEFAULT 1,
 FOREIGN KEY (main_requirement_id) REFERENCES rd_requirement(id)
) ENGINE=InnoDB;
CREATE TABLE rd_requirement_feedback (
 id BIGINT PRIMARY KEY, feedback_id BIGINT NOT NULL, requirement_id BIGINT NOT NULL,
 is_primary TINYINT NOT NULL,
 primary_feedback_id BIGINT GENERATED ALWAYS AS (IF(is_primary = 1, feedback_id, NULL)) STORED,
 UNIQUE KEY uq_primary (primary_feedback_id), UNIQUE KEY uq_pair (requirement_id, feedback_id),
 FOREIGN KEY (feedback_id) REFERENCES rd_feedback(id),
 FOREIGN KEY (requirement_id) REFERENCES rd_requirement(id)
) ENGINE=InnoDB;
CREATE TABLE rd_version_requirement (
 id BIGINT PRIMARY KEY, requirement_id BIGINT NOT NULL, version_id BIGINT NOT NULL,
 active TINYINT NOT NULL,
 active_requirement_id BIGINT GENERATED ALWAYS AS (IF(active = 1, requirement_id, NULL)) STORED,
 UNIQUE KEY uq_active (active_requirement_id),
 FOREIGN KEY (requirement_id) REFERENCES rd_requirement(id),
 FOREIGN KEY (version_id) REFERENCES rd_version(id)
) ENGINE=InnoDB;
-- Guards validate direct pointer writes; relation writes synchronize the pointer.
DELIMITER $$
CREATE TRIGGER req_insert BEFORE INSERT ON rd_requirement FOR EACH ROW
BEGIN
 IF NEW.current_version_id IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unbacked version pointer'; END IF;
END$$
CREATE TRIGGER fb_insert BEFORE INSERT ON rd_feedback FOR EACH ROW
BEGIN
 IF NEW.main_requirement_id IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unbacked primary pointer'; END IF;
END$$
CREATE TRIGGER req_update BEFORE UPDATE ON rd_requirement FOR EACH ROW
BEGIN
 DECLARE v BIGINT DEFAULT NULL;
 SELECT MAX(version_id) INTO v FROM rd_version_requirement WHERE requirement_id=OLD.id AND active=1;
 IF NOT (NEW.current_version_id <=> v) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='inconsistent version pointer'; END IF;
 IF NEW.id <> OLD.id THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable requirement id'; END IF;
END$$
CREATE TRIGGER fb_update BEFORE UPDATE ON rd_feedback FOR EACH ROW
BEGIN
 DECLARE r BIGINT DEFAULT NULL;
 SELECT MAX(requirement_id) INTO r FROM rd_requirement_feedback WHERE feedback_id=OLD.id AND is_primary=1;
 IF NOT (NEW.main_requirement_id <=> r) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='inconsistent primary pointer'; END IF;
 IF NEW.id <> OLD.id THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable feedback id'; END IF;
END$$
CREATE TRIGGER vr_insert BEFORE INSERT ON rd_version_requirement FOR EACH ROW
BEGIN
 DECLARE r BIGINT;
 SELECT id INTO r FROM rd_requirement WHERE id=NEW.requirement_id FOR UPDATE;
 IF NEW.active NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid active'; END IF;
END$$
CREATE TRIGGER rf_insert BEFORE INSERT ON rd_requirement_feedback FOR EACH ROW
BEGIN
 DECLARE f BIGINT;
 SELECT id INTO f FROM rd_feedback WHERE id=NEW.feedback_id FOR UPDATE;
 IF NEW.is_primary NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid primary'; END IF;
END$$
CREATE TRIGGER vr_update BEFORE UPDATE ON rd_version_requirement FOR EACH ROW
BEGIN
 DECLARE r BIGINT;
 SELECT id INTO r FROM rd_requirement WHERE id=OLD.requirement_id FOR UPDATE;
 IF NEW.active NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid active'; END IF;
 IF NEW.requirement_id <> OLD.requirement_id OR NEW.version_id <> OLD.version_id THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable relation endpoints'; END IF;
END$$
CREATE TRIGGER rf_update BEFORE UPDATE ON rd_requirement_feedback FOR EACH ROW
BEGIN
 DECLARE f BIGINT;
 SELECT id INTO f FROM rd_feedback WHERE id=OLD.feedback_id FOR UPDATE;
 IF NEW.is_primary NOT IN (0,1) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='invalid primary'; END IF;
 IF NEW.feedback_id <> OLD.feedback_id OR NEW.requirement_id <> OLD.requirement_id THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable relation endpoints'; END IF;
END$$
CREATE TRIGGER vr_sync_insert AFTER INSERT ON rd_version_requirement FOR EACH ROW
BEGIN
 IF NEW.active=1 THEN UPDATE rd_requirement SET current_version_id=NEW.version_id WHERE id=NEW.requirement_id; END IF;
END$$
CREATE TRIGGER rf_sync_insert AFTER INSERT ON rd_requirement_feedback FOR EACH ROW
BEGIN
 IF NEW.is_primary=1 THEN UPDATE rd_feedback SET main_requirement_id=NEW.requirement_id WHERE id=NEW.feedback_id; END IF;
END$$
CREATE TRIGGER vr_sync_update AFTER UPDATE ON rd_version_requirement FOR EACH ROW
BEGIN
 IF NEW.active <> OLD.active THEN UPDATE rd_requirement SET current_version_id=IF(NEW.active=1,NEW.version_id,NULL) WHERE id=NEW.requirement_id; END IF;
END$$
CREATE TRIGGER rf_sync_update AFTER UPDATE ON rd_requirement_feedback FOR EACH ROW
BEGIN
 IF NEW.is_primary <> OLD.is_primary THEN UPDATE rd_feedback SET main_requirement_id=IF(NEW.is_primary=1,NEW.requirement_id,NULL) WHERE id=NEW.feedback_id; END IF;
END$$
CREATE TRIGGER vr_sync_delete AFTER DELETE ON rd_version_requirement FOR EACH ROW
BEGIN
 IF OLD.active=1 THEN UPDATE rd_requirement SET current_version_id=NULL WHERE id=OLD.requirement_id; END IF;
END$$
CREATE TRIGGER rf_sync_delete AFTER DELETE ON rd_requirement_feedback FOR EACH ROW
BEGIN
 IF OLD.is_primary=1 THEN UPDATE rd_feedback SET main_requirement_id=NULL WHERE id=OLD.feedback_id; END IF;
END$$
DELIMITER ;

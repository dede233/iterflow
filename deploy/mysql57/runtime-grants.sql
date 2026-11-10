-- Template only. DBA creates fresh principals/passwords and edits DB/user/host.
-- Runtime must have NO DDL, TRIGGER, GRANT, global/admin or inherited broad grants.
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_comment` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_business_system` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_dictionary` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_file` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_permission` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_role` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_user` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_version` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_attachment_relation` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_business_module` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_dictionary_item` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_notification` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_operation_log` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_refresh_session` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_role_permission` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_user_role` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_feedback` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_release` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_requirement` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_requirement_feedback` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_version_requirement` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT ON `iterflow`.`alembic_version` TO 'iterflow_runtime'@'APP_HOST';
-- Physical long-key registry: read-only metadata; writes occur in DEFINER triggers.
GRANT SELECT ON `iterflow`.`iterflow_file_key_node` TO 'iterflow_runtime'@'APP_HOST';

GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_requirement_participant` TO 'iterflow_runtime'@'APP_HOST';

-- Collaboration workflow and transactional notification delivery.
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_feedback_recipient` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_requirement_actor` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_requirement_step` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_collaboration_event` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_mail_preference` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_notification_delivery` TO 'iterflow_runtime'@'APP_HOST';

-- Update announcements and account-wide read acknowledgements (mysql57_0014).
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_announcement` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_announcement_read` TO 'iterflow_runtime'@'APP_HOST';

-- Multi-target release directory, plans and actual records (mysql57_0015).
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`sys_release_target` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_release_batch` TO 'iterflow_runtime'@'APP_HOST';
GRANT SELECT, INSERT, UPDATE, DELETE ON `iterflow`.`rd_release_batch_target` TO 'iterflow_runtime'@'APP_HOST';

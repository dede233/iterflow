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

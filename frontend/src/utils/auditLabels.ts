export const auditEntityLabels: Record<string, string> = {
  FEEDBACK: '反馈',
  REQUIREMENT: '需求',
  VERSION: '版本',
  RELEASE: '发布记录',
  USER: '用户',
  ROLE: '角色',
  AUTH: '账号认证',
  SYSTEM: '系统设置',
  DICTIONARY: '数据字典',
  BUSINESS_SYSTEM: '业务系统',
  BUSINESS_MODULE: '业务模块',
}

export const auditActionLabels: Record<string, string> = {
  CREATE: '创建',
  UPDATE: '更新',
  STATUS_CHANGE: '变更状态',
  ATTACHMENT_ADD: '添加附件',
  CONVERT_REQUIREMENT: '转为需求',
  CREATE_FROM_FEEDBACK: '由反馈创建',
  COMMENT_CREATE: '添加评论',
  VERSION_REQUIREMENT_ADD: '加入版本',
  VERSION_REQUIREMENT_REMOVE: '移出版本',
  VERSION_REQUIREMENT_MOVE: '迁移版本',
  VERSION_PUBLISH: '发布版本',
  RELEASE_CREATE: '创建发布记录',
  ROLE_CREATE: '创建角色',
  ROLE_UPDATE: '更新角色',
  ROLE_DELETE: '删除角色',
  ROLE_PERMISSION_UPDATE: '更新角色权限',
  ROLES_UPDATE: '调整用户角色',
  SYSTEM_CREATE: '创建业务系统',
  SYSTEM_UPDATE: '更新业务系统',
  MODULE_CREATE: '创建业务模块',
  MODULE_UPDATE: '更新业务模块',
  LOGIN: '登录',
  LOGIN_FAILED: '登录失败',
  LOGOUT: '退出登录',
  PASSWORD_CHANGE: '修改密码',
  PASSWORD_CHANGE_FAILED: '修改密码失败',
}

export const auditEntityOptions = Object.entries(auditEntityLabels).map(([value, label]) => ({ value, label }))
export const auditActionOptions = Object.entries(auditActionLabels).map(([value, label]) => ({ value, label }))

export function auditEntityLabel(code: string): string {
  return auditEntityLabels[code] ?? `未知实体（${code}）`
}

export function auditActionLabel(code: string): string {
  return auditActionLabels[code] ?? `未知操作（${code}）`
}

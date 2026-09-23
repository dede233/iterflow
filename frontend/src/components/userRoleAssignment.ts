import type { UserUpdatePayload } from '@/api/users'
import type { CurrentUser } from '@/types/auth'
import type { RoleItem, UserItem } from '@/types/system'

export interface UserBasicForm {
  display_name: string
  email: string | null
  mobile: string | null
}

export const ROLE_DEFINITION_READ_PERMISSIONS = [
  'sys.role.view',
  'sys.role.manage',
  'sys.user.role.assign',
]

export function canLoadRoleDefinitions(
  currentUser: CurrentUser | null,
  hasPermission: (permission: string | string[]) => boolean,
): boolean {
  return (
    currentUser?.data_scope === 'ALL' &&
    hasPermission(ROLE_DEFINITION_READ_PERMISSIONS)
  )
}

export function isSuperAdminRole(role: RoleItem): boolean {
  return role.is_system && role.code === 'SUPER_ADMIN'
}

export function findSuperAdminRole(roles: RoleItem[]): RoleItem | undefined {
  return roles.find(isSuperAdminRole)
}

export function isCurrentUserSuperAdmin(
  currentUser: CurrentUser | null,
  roles: RoleItem[],
): boolean {
  const superAdminRole = findSuperAdminRole(roles)
  return Boolean(
    currentUser && superAdminRole && currentUser.role_ids.includes(superAdminRole.id),
  )
}

export function isUserSuperAdmin(user: UserItem, roles: RoleItem[]): boolean {
  const superAdminRole = findSuperAdminRole(roles)
  return Boolean(superAdminRole && user.role_ids.includes(superAdminRole.id))
}

export function buildUserBasicUpdatePayload(
  form: UserBasicForm,
  revision: number,
): UserUpdatePayload {
  return {
    display_name: form.display_name.trim(),
    email: form.email?.trim() || null,
    mobile: form.mobile?.trim() || null,
    revision,
  }
}

export function buildUserRoleUpdateRequest(user: UserItem, roleIds: number[]) {
  return {
    userId: user.id,
    roleIds: [...roleIds].sort((left, right) => left - right),
    revision: user.revision,
  }
}

export function canOperatorChangeUserStatus(
  user: UserItem,
  roles: RoleItem[],
  operatorIsSuperAdmin: boolean,
): boolean {
  return operatorIsSuperAdmin || !isUserSuperAdmin(user, roles)
}

export function statusConfirmationMessage(
  user: UserItem,
  roles: RoleItem[],
  nextStatus: UserItem['status'],
): string {
  const action = nextStatus === 'ACTIVE' ? '启用' : '停用'
  const warning =
    nextStatus !== 'ACTIVE' && isUserSuperAdmin(user, roles)
      ? ' 如果这是最后一个有效超级管理员，系统将拒绝该操作。'
      : ''
  return `确定要${action}用户“${user.display_name}”吗？${warning}`
}

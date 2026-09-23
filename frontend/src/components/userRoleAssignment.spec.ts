import { describe, expect, it } from 'vitest'
import {
  buildUserBasicUpdatePayload,
  buildUserRoleUpdateRequest,
  canLoadRoleDefinitions,
  canOperatorChangeUserStatus,
  findSuperAdminRole,
  isCurrentUserSuperAdmin,
  isSuperAdminRole,
  isUserSuperAdmin,
  statusConfirmationMessage,
} from '@/components/userRoleAssignment'
import type { CurrentUser } from '@/types/auth'
import type { RoleItem, UserItem } from '@/types/system'

const roles: RoleItem[] = [
  {
    id: 1,
    code: 'SUPER_ADMIN',
    name: '超级管理员',
    data_scope: 'ALL',
    enabled: true,
    is_system: true,
    revision: 1,
    permission_ids: [],
  },
  {
    id: 2,
    code: 'ADMINISTRATOR',
    name: '用户管理员',
    data_scope: 'ALL',
    enabled: true,
    is_system: false,
    revision: 1,
    permission_ids: [],
  },
]

function user(roleIds: number[]): UserItem {
  return {
    id: 8,
    username: 'target',
    display_name: '目标用户',
    email: null,
    mobile: null,
    status: 'ACTIVE',
    revision: 6,
    role_ids: roleIds,
  }
}

function currentUser(roleIds: number[]): CurrentUser {
  return {
    id: 3,
    username: 'operator',
    display_name: '操作人',
    email: null,
    status: 'ACTIVE',
    revision: 1,
    role_ids: roleIds,
    permission_codes: ['sys.user.role.assign'],
    data_scope: 'ALL',
    must_change_password: false,
  }
}

describe('user role assignment security UX', () => {
  it('recognizes SUPER_ADMIN only from the enabled system role relation', () => {
    expect(findSuperAdminRole(roles)?.id).toBe(1)
    expect(isSuperAdminRole(roles[0])).toBe(true)
    expect(isCurrentUserSuperAdmin(currentUser([1]), roles)).toBe(true)
    expect(isCurrentUserSuperAdmin(currentUser([2]), roles)).toBe(false)
    expect(isUserSuperAdmin(user([1]), roles)).toBe(true)
  })

  it('keeps profile edits separate from role assignment and uses latest revisions', () => {
    const basic = buildUserBasicUpdatePayload(
      { display_name: ' 新名称 ', email: ' user@example.test ', mobile: ' 13800000000 ' },
      5,
    )
    expect(basic).toEqual({
      display_name: '新名称',
      email: 'user@example.test',
      mobile: '13800000000',
      revision: 5,
    })
    expect(basic).not.toHaveProperty('role_ids')
    expect(buildUserRoleUpdateRequest(user([2]), [2, 1])).toEqual({
      userId: 8,
      roleIds: [1, 2],
      revision: 6,
    })
  })

  it('loads role definitions for ALL-scope role assigners without role-view permission', () => {
    const assigner = currentUser([2])
    const hasPermission = (permission: string | string[]) => {
      const required = Array.isArray(permission) ? permission : [permission]
      return required.some((code) => assigner.permission_codes.includes(code))
    }

    expect(canLoadRoleDefinitions(assigner, hasPermission)).toBe(true)
    expect(
      canLoadRoleDefinitions({ ...assigner, data_scope: 'SELF' }, hasPermission),
    ).toBe(false)
    expect(canLoadRoleDefinitions(assigner, () => false)).toBe(false)
  })

  it('protects SUPER_ADMIN status controls without estimating the last admin', () => {
    const superAdmin = user([1])
    expect(canOperatorChangeUserStatus(superAdmin, roles, false)).toBe(false)
    expect(canOperatorChangeUserStatus(superAdmin, roles, true)).toBe(true)
    expect(canOperatorChangeUserStatus(user([2]), roles, false)).toBe(true)
    expect(statusConfirmationMessage(superAdmin, roles, 'DISABLED')).toContain(
      '如果这是最后一个有效超级管理员，系统将拒绝该操作',
    )
  })
})

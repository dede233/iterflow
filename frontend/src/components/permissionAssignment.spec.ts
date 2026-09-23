import { describe, expect, it, vi } from 'vitest'
import {
  addedSensitivePermissions,
  buildPermissionUpdateRequest,
  buildRoleBasicUpdatePayload,
  confirmAddedSensitivePermissions,
  groupPermissions,
  setPermissionGroupSelection,
} from '@/components/permissionAssignment'
import type { PermissionItem, RoleItem } from '@/types/system'

const permissions: PermissionItem[] = [
  {
    id: 1,
    code: 'rd.feedback.view',
    name: '反馈查看',
    category: 'BUTTON',
    group: 'Feedback / 反馈',
    sensitive: false,
    deprecated: false,
    replacement_code: null,
  },
  {
    id: 2,
    code: 'rd.feedback.edit',
    name: '编辑反馈',
    category: 'BUTTON',
    group: 'Feedback / 反馈',
    sensitive: false,
    deprecated: false,
    replacement_code: null,
  },
  {
    id: 3,
    code: 'sys.role.manage',
    name: '角色管理',
    category: 'BUTTON',
    group: 'Role / 角色权限',
    sensitive: true,
    deprecated: false,
    replacement_code: null,
  },
  {
    id: 4,
    code: 'sys.user.role.assign',
    name: '分配用户角色',
    category: 'BUTTON',
    group: 'User / 用户管理',
    sensitive: true,
    deprecated: false,
    replacement_code: null,
  },
]

describe('permission assignment behavior', () => {
  it('groups permissions and supports selecting or clearing one module', () => {
    const groups = groupPermissions(permissions)
    expect(groups.map((group) => group.name)).toEqual([
      'Feedback / 反馈',
      'Role / 角色权限',
      'User / 用户管理',
    ])

    const selected = setPermissionGroupSelection([], groups[0], true)
    expect(selected).toEqual([1, 2])
    expect(setPermissionGroupSelection([1, 2, 3], groups[0], false)).toEqual([3])
  })

  it('confirms only newly added sensitive permissions', async () => {
    expect(addedSensitivePermissions([3], [1, 3, 4], permissions).map((item) => item.id)).toEqual([
      4,
    ])

    const confirmSensitive = vi.fn(() => Promise.resolve())
    await expect(
      confirmAddedSensitivePermissions([1], [1, 3, 4], permissions, confirmSensitive),
    ).resolves.toBe(true)
    expect(confirmSensitive).toHaveBeenCalledOnce()
    expect(confirmSensitive.mock.calls[0][0]).toContain('角色管理、分配用户角色')

    const confirmOrdinary = vi.fn(() => Promise.resolve())
    await expect(
      confirmAddedSensitivePermissions([], [1, 2], permissions, confirmOrdinary),
    ).resolves.toBe(true)
    expect(confirmOrdinary).not.toHaveBeenCalled()
  })

  it('keeps basic role edits separate and saves permissions with the latest revision', () => {
    const basicPayload = buildRoleBasicUpdatePayload(
      { code: ' CUSTOM ', name: ' 自定义角色 ', data_scope: 'ALL', enabled: false },
      8,
    )
    expect(basicPayload).toEqual({
      code: 'CUSTOM',
      name: '自定义角色',
      data_scope: 'ALL',
      enabled: false,
      revision: 8,
    })
    expect(basicPayload).not.toHaveProperty('permission_ids')

    const role: RoleItem = {
      id: 7,
      code: 'CUSTOM',
      name: '自定义角色',
      data_scope: 'ALL',
      enabled: true,
      is_system: false,
      revision: 9,
      permission_ids: [1],
    }
    expect(buildPermissionUpdateRequest(role, [4, 2])).toEqual({
      roleId: 7,
      permissionIds: [2, 4],
      revision: 9,
    })
  })
})

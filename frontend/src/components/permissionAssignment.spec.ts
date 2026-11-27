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
    const sections = groupPermissions(permissions)
    expect(sections.map((section) => section.name)).toEqual([
      'Feedback / 反馈',
      'Role / 角色权限',
      'User / 用户管理',
    ])
    expect(sections.every((section) => !section.nested)).toBe(true)

    const [feedback] = sections[0].groups
    const selected = setPermissionGroupSelection([], feedback, true)
    expect(selected).toEqual([1, 2])
    expect(setPermissionGroupSelection([1, 2, 3], feedback, false)).toEqual([3])
  })

  it('keeps each operations subgroup independently selectable under one parent', () => {
    const sections = groupPermissions([
      permissions[0],
      { ...permissions[0], id: 5, code: 'ops.ad_production.view', group: '物料制作', parent_group: '运营协作' },
      { ...permissions[0], id: 6, code: 'ops.merchant_ad.view', group: '商家广告', parent_group: '运营协作' },
      { ...permissions[0], id: 7, code: 'ops.ad_production.create', group: '物料制作', parent_group: '运营协作' },
    ])
    expect(sections.map((section) => section.name)).toEqual(['Feedback / 反馈', '运营协作'])
    expect(sections[1].nested).toBe(true)
    const [material, merchant] = sections[1].groups
    expect(material.name).toBe('物料制作')
    expect(merchant.name).toBe('商家广告')
    expect(setPermissionGroupSelection([1, 6], material, true)).toEqual([1, 6, 5, 7])
    expect(setPermissionGroupSelection([1, 5, 6, 7], merchant, false)).toEqual([1, 5, 7])
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
      assignable: true,
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

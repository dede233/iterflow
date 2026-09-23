import type { RoleUpdatePayload } from '@/api/roles'
import type { PermissionItem, RoleItem } from '@/types/system'

export interface PermissionGroup {
  name: string
  permissions: PermissionItem[]
}

export interface RoleBasicForm {
  code: string
  name: string
  data_scope: 'SELF' | 'ALL'
  enabled: boolean
}

export function groupPermissions(permissions: PermissionItem[]): PermissionGroup[] {
  const grouped = new Map<string, PermissionItem[]>()
  for (const permission of permissions) {
    const items = grouped.get(permission.group) ?? []
    items.push(permission)
    grouped.set(permission.group, items)
  }
  return [...grouped].map(([name, items]) => ({ name, permissions: items }))
}

export function setPermissionGroupSelection(
  selectedIds: number[],
  group: PermissionGroup,
  selected: boolean,
): number[] {
  const groupIds = new Set(group.permissions.map((permission) => permission.id))
  if (!selected) return selectedIds.filter((permissionId) => !groupIds.has(permissionId))
  return [...new Set([...selectedIds, ...groupIds])]
}

export function addedSensitivePermissions(
  originalIds: number[],
  nextIds: number[],
  permissions: PermissionItem[],
): PermissionItem[] {
  const original = new Set(originalIds)
  const next = new Set(nextIds)
  return permissions.filter(
    (permission) => permission.sensitive && next.has(permission.id) && !original.has(permission.id),
  )
}

export async function confirmAddedSensitivePermissions(
  originalIds: number[],
  nextIds: number[],
  permissions: PermissionItem[],
  confirm: (message: string) => Promise<unknown>,
): Promise<boolean> {
  const added = addedSensitivePermissions(originalIds, nextIds, permissions)
  if (!added.length) return true
  const names = added.map((permission) => permission.name).join('、')
  try {
    await confirm(`本次将为角色新增高权限能力：${names}。确认继续？`)
    return true
  } catch {
    return false
  }
}

export function buildRoleBasicUpdatePayload(
  form: RoleBasicForm,
  revision: number,
): RoleUpdatePayload {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    data_scope: form.data_scope,
    enabled: form.enabled,
    revision,
  }
}

export function buildPermissionUpdateRequest(role: RoleItem, permissionIds: number[]) {
  return {
    roleId: role.id,
    permissionIds: [...permissionIds].sort((left, right) => left - right),
    revision: role.revision,
  }
}

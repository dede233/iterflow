import type { RoleUpdatePayload } from '@/api/roles'
import type { PermissionItem, RoleItem } from '@/types/system'

export interface PermissionGroup {
  key: string
  name: string
  permissions: PermissionItem[]
}

interface PermissionSection {
  key: string
  name: string
  nested: boolean
  groups: PermissionGroup[]
}

export interface RoleBasicForm {
  code: string
  name: string
  data_scope: 'SELF' | 'ALL'
  enabled: boolean
}

export function groupPermissions(permissions: PermissionItem[]): PermissionSection[] {
  const sections = new Map<string, PermissionSection>()
  const groups = new Map<string, PermissionGroup>()
  for (const permission of permissions) {
    const parent = permission.parent_group || null
    const name = parent ?? permission.group
    const sectionKey = parent ? `parent:${name}` : `group:${name}`
    let section = sections.get(sectionKey)
    if (!section) {
      section = { key: sectionKey, name, nested: Boolean(parent), groups: [] }
      sections.set(sectionKey, section)
    }
    const groupKey = JSON.stringify([parent, permission.group])
    let group = groups.get(groupKey)
    if (!group) {
      group = { key: groupKey, name: permission.group, permissions: [] }
      groups.set(groupKey, group)
      section.groups.push(group)
    }
    group.permissions.push(permission)
  }
  return [...sections.values()]
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

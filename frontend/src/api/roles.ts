import { api } from './client'
import type { PermissionItem, RoleItem } from '@/types/system'

export interface RoleCreatePayload {
  code: string
  name: string
  data_scope: 'SELF' | 'ALL'
  permission_ids: number[]
}

export interface RoleUpdatePayload {
  code?: string
  name?: string
  data_scope?: 'SELF' | 'ALL'
  enabled?: boolean
  revision: number
}

export const listRoles = () => api.get<RoleItem[]>('/roles').then((response) => response.data)

export const listPermissions = () =>
  api.get<PermissionItem[]>('/roles/permissions').then((response) => response.data)

export const createRole = (payload: RoleCreatePayload) =>
  api.post<RoleItem>('/roles', payload).then((response) => response.data)

export const updateRole = (roleId: number, payload: RoleUpdatePayload) =>
  api.patch<RoleItem>(`/roles/${roleId}`, payload).then((response) => response.data)

export const updateRolePermissions = (roleId: number, permissionIds: number[], revision: number) =>
  api
    .put<RoleItem>(`/roles/${roleId}/permissions`, {
      permission_ids: permissionIds,
      revision,
    })
    .then((response) => response.data)

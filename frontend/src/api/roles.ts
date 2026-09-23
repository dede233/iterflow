import { api } from './client'
import type {
  PermissionItem,
  RoleCreatePayload,
  RoleDeleteOut,
  RoleItem,
  RolePermissionUpdatePayload,
  RoleUpdatePayload,
} from '@/types/system'

export type { RoleUpdatePayload } from '@/types/system'

export const listRoles = () => api.get<RoleItem[]>('/roles').then((response) => response.data)

export const getRole = (roleId: number) =>
  api.get<RoleItem>(`/roles/${roleId}`).then((response) => response.data)

export const listPermissions = () =>
  api.get<PermissionItem[]>('/roles/permissions').then((response) => response.data)

export const createRole = (payload: RoleCreatePayload) =>
  api.post<RoleItem>('/roles', payload).then((response) => response.data)

export const updateRole = (roleId: number, payload: RoleUpdatePayload) =>
  api.patch<RoleItem>(`/roles/${roleId}`, payload).then((response) => response.data)

export const updateRolePermissions = (roleId: number, payload: RolePermissionUpdatePayload) =>
  api
    .put<RoleItem>(`/roles/${roleId}/permissions`, payload)
    .then((response) => response.data)

export const deleteRole = (roleId: number) =>
  api.delete<RoleDeleteOut>(`/roles/${roleId}`).then((response) => response.data)

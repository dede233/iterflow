import { api } from './client'
import type { UserItem } from '@/types/system'
import type { PageResult } from '@/types/domain'

export interface UserCreatePayload {
  username: string
  display_name: string
  email: string | null
  mobile: string | null
  password: string
  role_ids: number[]
}

export interface UserUpdatePayload {
  display_name?: string
  email?: string | null
  mobile?: string | null
  revision: number
}

export const listUsers = () => api.get<PageResult<UserItem>>('/users').then((response) => response.data)

export const createUser = (payload: UserCreatePayload) =>
  api.post<UserItem>('/users', payload).then((response) => response.data)

export const updateUser = (userId: number, payload: UserUpdatePayload) =>
  api.patch<UserItem>(`/users/${userId}`, payload).then((response) => response.data)

export const updateUserStatus = (userId: number, status: UserItem['status'], revision: number) =>
  api.patch<UserItem>(`/users/${userId}/status`, { status, revision }).then((response) => response.data)

export const updateUserRoles = (userId: number, roleIds: number[], revision: number) =>
  api
    .put<UserItem>(`/users/${userId}/roles`, { role_ids: roleIds, revision })
    .then((response) => response.data)

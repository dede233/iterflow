import { api } from './client'
import type {
  UserCreatePayload,
  UserItem,
  UserRoleUpdatePayload,
  UserStatusChangePayload,
  UserUpdatePayload,
} from '@/types/system'
import type { components } from '@/types/openapi.generated'

export type { UserUpdatePayload } from '@/types/system'
type UserPage = components['schemas']['UserPage']

export const listUsers = () => api.get<UserPage>('/users').then((response) => response.data)

export const createUser = (payload: UserCreatePayload) =>
  api.post<UserItem>('/users', payload).then((response) => response.data)

export const updateUser = (userId: number, payload: UserUpdatePayload) =>
  api.patch<UserItem>(`/users/${userId}`, payload).then((response) => response.data)

export const updateUserStatus = (
  userId: number,
  payload: UserStatusChangePayload,
) =>
  api.patch<UserItem>(`/users/${userId}/status`, payload).then((response) => response.data)

export const updateUserRoles = (userId: number, payload: UserRoleUpdatePayload) =>
  api
    .put<UserItem>(`/users/${userId}/roles`, payload)
    .then((response) => response.data)

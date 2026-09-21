import { api } from './client'
import type { CurrentUser, TokenPair } from '@/types/auth'

export const loginApi = (username: string, password: string) =>
  api.post<TokenPair>('/auth/login', { username, password }, { skipAuthRefresh: true }).then((r) => r.data)

export const logoutApi = (refreshToken: string) =>
  api.post('/auth/logout', { refresh_token: refreshToken }, { skipAuthRefresh: true })

export const currentUserApi = () => api.get<CurrentUser>('/auth/me').then((r) => r.data)

export const changePasswordApi = (currentPassword: string, newPassword: string) =>
  api
    .post(
      '/auth/change-password',
      {
        current_password: currentPassword,
        new_password: newPassword,
      },
      { skipAuthRefresh: true },
    )
    .then((r) => r.data)

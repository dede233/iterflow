import { api } from './client'
import type { CurrentUser, TokenPair } from '@/types/auth'

export const loginApi = (username: string, password: string) =>
  api
    .post<TokenPair>('/auth/login', { username, password }, { skipAuth: true, skipAuthRefresh: true })
    .then((r) => r.data)

export const logoutApi = (refreshToken: string) =>
  api.post('/auth/logout', { refresh_token: refreshToken }, { skipAuth: true, skipAuthRefresh: true })

export const currentUserApi = () => api.get<CurrentUser>('/auth/me').then((r) => r.data)

export const changePasswordApi = (currentPassword: string, newPassword: string) =>
  api
    .post<TokenPair>(
      '/auth/change-password',
      {
        current_password: currentPassword,
        new_password: newPassword,
      },
      // The access token must be sent (this is the forced first-login change),
      // but a 401 here means a wrong current password, not an expired session,
      // so never trigger a silent refresh + replay.
      { skipAuthRefresh: true },
    )
    .then((r) => r.data)

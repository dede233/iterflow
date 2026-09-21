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
  // The forced first-login change relies on current_user, so the access token
  // must be attached (no skipAuth). No skipAuthRefresh either: if the access
  // token has expired by the time the user submits, the 401 goes through the
  // single-flight refresh + replay like any other authenticated request.
  api
    .post<TokenPair>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    .then((r) => r.data)

import { defineStore } from 'pinia'
import { changePasswordApi, currentUserApi, loginApi, logoutApi } from '@/api/auth'
import { clearStoredTokens, getStoredTokens, setStoredTokens } from '@/auth/session'
import type { CurrentUser, TokenPair } from '@/types/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getStoredTokens()?.accessToken ?? '',
    user: null as CurrentUser | null,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
    permissionCodes: (state) => state.user?.permission_codes ?? [],
  },
  actions: {
    applyTokens(tokens: TokenPair): void {
      this.accessToken = tokens.access_token
      setStoredTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token })
    },
    hasPermission(permission: string | string[]): boolean {
      const required = Array.isArray(permission) ? permission : [permission]
      return this.permissionCodes.includes('*') || required.some((code) => this.permissionCodes.includes(code))
    },
    async loadCurrentUser(): Promise<CurrentUser> {
      const user = await currentUserApi()
      this.user = user
      this.initialized = true
      return user
    },
    async restoreSession(): Promise<boolean> {
      if (!getStoredTokens()) {
        this.reset()
        return false
      }
      try {
        await this.loadCurrentUser()
        return true
      } catch {
        this.reset()
        return false
      }
    },
    async login(username: string, password: string): Promise<CurrentUser> {
      const tokens = await loginApi(username, password)
      this.applyTokens(tokens)
      return this.loadCurrentUser()
    },
    async changePassword(currentPassword: string, newPassword: string): Promise<void> {
      const response = await changePasswordApi(currentPassword, newPassword)
      if (response.access_token && response.refresh_token) this.applyTokens(response as TokenPair)
      await this.loadCurrentUser()
    },
    async logout(): Promise<void> {
      const refreshToken = getStoredTokens()?.refreshToken
      try {
        if (refreshToken) await logoutApi(refreshToken)
      } finally {
        this.reset()
      }
    },
    reset(): void {
      this.accessToken = ''
      this.user = null
      this.initialized = true
      clearStoredTokens()
    },
  },
})

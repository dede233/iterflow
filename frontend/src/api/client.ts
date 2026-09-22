import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clearStoredTokens, getStoredTokens, setStoredTokens } from '@/auth/session'
import type { TokenPair } from '@/types/auth'

declare module 'axios' {
  export interface AxiosRequestConfig {
    _retry?: boolean
    // Do not attach the stored access token (login/refresh/logout carry their own credential).
    skipAuth?: boolean
    // Do not attempt a silent refresh + replay when the response is 401.
    skipAuthRefresh?: boolean
    // Do not pop the global edit-conflict dialog on 409 (the caller renders the
    // conflict/checks inline instead, e.g. the publish pre-check preview).
    skipConflictAlert?: boolean
  }
}

// Backend business code for an invalid/expired Access Token (HTTP 401). Only
// this code should trigger a silent refresh. Other 401s — wrong current
// password (40112), disabled user (40103), missing credentials (40100) — are
// terminal and must be surfaced without touching the refresh endpoint.
export const ACCESS_TOKEN_EXPIRED_CODE = 40101

export const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })

const refreshClient = axios.create({ baseURL: '/api/v1', timeout: 15000 })
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const tokens = getStoredTokens()
  if (!tokens) throw new Error('No refresh token is available')

  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post<TokenPair>('/auth/refresh', { refresh_token: tokens.refreshToken })
      .then((response) => {
        setStoredTokens({
          accessToken: response.data.access_token,
          refreshToken: response.data.refresh_token,
        })
        return response.data.access_token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

api.interceptors.request.use((config) => {
  const token = getStoredTokens()?.accessToken
  if (token && !config.skipAuth) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (
      error.response?.status === 401 &&
      error.response?.data?.code === ACCESS_TOKEN_EXPIRED_CODE &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.skipAuthRefresh
    ) {
      originalRequest._retry = true
      try {
        const accessToken = await refreshAccessToken()
        originalRequest.headers = originalRequest.headers ?? {}
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return api(originalRequest)
      } catch {
        clearStoredTokens()
        if (window.location.pathname !== '/login') {
          window.location.assign(`/login?redirect=${encodeURIComponent(window.location.pathname)}`)
        }
      }
    }
    if (error.response?.status === 409 && !originalRequest?.skipConflictAlert) {
      await ElMessageBox.alert(error.response.data?.message ?? '数据已被其他用户修改，请刷新后重试', '编辑冲突', { type: 'warning' })
    } else if (error.response?.status === 403) {
      ElMessage.error('你没有权限执行该操作')
    }
    return Promise.reject(error)
  },
)

import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'
import { setStoredTokens } from '@/auth/session'

// --- Mutable state the mock transport closes over (reset per test) -----------
let refreshCalls = 0
let changePasswordCalls = 0

const EXPIRED_ACCESS = 'access-expired'
const FRESH_ACCESS = 'access-fresh-after-refresh'
const VALID_ACCESS = 'access-valid'
const REFRESH_TOKEN = 'refresh-valid'
const CORRECT_CURRENT = 'Correct!2026'

function authHeader(config: InternalAxiosRequestConfig): string {
  const headers = config.headers as unknown as {
    Authorization?: string
    get?: (name: string) => unknown
  }
  return String(headers?.Authorization ?? headers?.get?.('Authorization') ?? '')
}

function ok(config: InternalAxiosRequestConfig, data: unknown): AxiosResponse {
  return { data, status: 200, statusText: 'OK', headers: {}, config }
}

function fail(config: InternalAxiosRequestConfig, status: number, code: number, message: string) {
  return Promise.reject({
    isAxiosError: true,
    config,
    message,
    response: { data: { code, message }, status, statusText: 'ERR', headers: {}, config },
  })
}

const TOKEN_PAIR = (access: string) => ({
  access_token: access,
  refresh_token: 'refresh-rotated',
  token_type: 'bearer',
  must_change_password: false,
})

// A single fake transport shared by both the `api` and `refreshClient`
// instances (they inherit axios.defaults.adapter, set before the import below).
axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  const url = config.url ?? ''

  if (url.endsWith('/auth/refresh')) {
    refreshCalls += 1
    return ok(config, TOKEN_PAIR(FRESH_ACCESS))
  }

  if (url.endsWith('/auth/change-password')) {
    changePasswordCalls += 1
    const body = JSON.parse(String(config.data ?? '{}'))
    // Wrong current password is a terminal 40112 regardless of the token.
    if (body.current_password !== CORRECT_CURRENT) {
      return fail(config, 401, 40112, '当前密码错误')
    }
    // A stale access token yields 40101 (the only code that should refresh).
    if (authHeader(config) === `Bearer ${EXPIRED_ACCESS}`) {
      return fail(config, 401, 40101, '登录凭证无效或已过期')
    }
    return ok(config, TOKEN_PAIR('access-after-change'))
  }

  return ok(config, {})
}

// Imported AFTER the default adapter is installed so the module-level
// axios.create() instances pick up the fake transport.
const { changePasswordApi } = await import('@/api/auth')

beforeEach(() => {
  refreshCalls = 0
  changePasswordCalls = 0
  localStorage.clear()
})

describe('change-password 401 handling', () => {
  it('expired access + correct current password -> refresh once, then change succeeds', async () => {
    setStoredTokens({ accessToken: EXPIRED_ACCESS, refreshToken: REFRESH_TOKEN })

    const result = await changePasswordApi(CORRECT_CURRENT, 'BrandNew!2026')

    expect(result.must_change_password).toBe(false)
    expect(refreshCalls).toBe(1) // single-flight refresh fired on 40101
    expect(changePasswordCalls).toBe(2) // initial 401 + replay after refresh
    // Refreshed access token was persisted for subsequent requests.
    expect(localStorage.getItem('iterflow.access_token')).toBe(FRESH_ACCESS)
  })

  it('valid access + wrong current password -> 40112 and the refresh endpoint is never called', async () => {
    setStoredTokens({ accessToken: VALID_ACCESS, refreshToken: REFRESH_TOKEN })

    await expect(changePasswordApi('WrongCurrent!2026', 'BrandNew!2026')).rejects.toMatchObject({
      response: { data: { code: 40112 } },
    })

    expect(refreshCalls).toBe(0) // a wrong-password 401 must not touch /auth/refresh
    expect(changePasswordCalls).toBe(1) // no replay
  })
})

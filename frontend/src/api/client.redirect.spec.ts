import axios, { type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('element-plus', () => ({ ElMessage: { warning: vi.fn(), error: vi.fn() } }))
import { getStoredTokens, setStoredTokens } from '@/auth/session'

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); localStorage.clear() })

describe('expired access and failed refresh', () => {
  it('single-flights refresh and redirects only once to the full Hash target', async () => {
    vi.resetModules()
    let refreshCalls = 0
    let rejectRefresh!: (value: unknown) => void
    const refresh = new Promise<never>((_, reject) => { rejectRefresh = reject })
    axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      if (config.url === '/auth/refresh') { refreshCalls++; return refresh }
      throw { config, response: { status: 401, data: { code: 40101 } } }
    }
    const assign = vi.fn()
    vi.stubGlobal('window', { location: { hash: '#/requirements/42?tab=info', assign } })
    setStoredTokens({ accessToken: 'expired', refreshToken: 'invalid' })
    const { api } = await import('./client')
    const a = api.get('/requirements/42').catch(e => e)
    const b = api.get('/versions/2').catch(e => e)
    await vi.waitFor(() => expect(refreshCalls).toBe(1))
    rejectRefresh(new Error('invalid refresh'))
    await Promise.all([a, b])
    expect(refreshCalls).toBe(1)
    expect(assign).toHaveBeenCalledExactlyOnceWith('/#/login?redirect=%2Frequirements%2F42%3Ftab%3Dinfo')
    expect(getStoredTokens()).toBeNull()
  })
  it('does not navigate away from an already visible login route', async () => {
    vi.resetModules()
    axios.defaults.adapter = async config => { throw { config, response: { status: 401, data: { code: 40101 } } } }
    const assign = vi.fn()
    vi.stubGlobal('window', { location: { hash: '#/login?redirect=%2Frequirements', assign } })
    setStoredTokens({ accessToken: 'expired', refreshToken: 'invalid' })
    const { api } = await import('./client')
    await expect(api.get('/requirements')).rejects.toBeDefined()
    expect(assign).not.toHaveBeenCalled()
    expect(getStoredTokens()).toBeNull()
  })
})

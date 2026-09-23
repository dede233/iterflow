import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  ElMessageBox: { alert: vi.fn(() => Promise.resolve()) },
}))

let lastRequest: InternalAxiosRequestConfig | null = null

const responseData = {
  data_scope: 'SELF',
  feedback: { pending_count: 2, total_count: 3, by_status: { NEW: 1, ACCEPTED: 1 } },
  requirements: null,
  versions: null,
  releases: null,
}

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  lastRequest = config
  return { data: responseData, status: 200, statusText: 'ok', headers: {}, config }
}

const { getDashboardOverview } = await import('@/api/dashboard')

beforeEach(() => {
  lastRequest = null
  localStorage.clear()
})

describe('dashboard API', () => {
  it('loads the permission-aware overview', async () => {
    await expect(getDashboardOverview()).resolves.toEqual(responseData)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/dashboard/overview')
  })
})

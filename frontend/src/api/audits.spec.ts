import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  ElMessageBox: { alert: vi.fn(() => Promise.resolve()) },
}))

let lastRequest: InternalAxiosRequestConfig | null = null

axios.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
  lastRequest = config
  return { data: { items: [], page: 1, size: 20, total: 0 }, status: 200, statusText: 'ok', headers: {}, config }
}

const { getAudit, listAudits } = await import('@/api/audits')

beforeEach(() => {
  lastRequest = null
  localStorage.clear()
})

describe('audit API DTO mapping', () => {
  it('lists audits with pagination and filters', async () => {
    await listAudits({
      page: 2,
      size: 10,
      entity_type: 'REQUIREMENT',
      entity_id: 7,
      action: 'STATUS_CHANGE',
      operator_id: 3,
      time_from: '2026-01-01T00:00:00Z',
      time_to: '2026-01-31T00:00:00Z',
    })
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/audits')
    expect(lastRequest?.params).toMatchObject({ page: 2, size: 10, entity_type: 'REQUIREMENT' })
  })

  it('loads a single audit record for the detail drawer', async () => {
    await getAudit(42)
    expect(lastRequest?.method).toBe('get')
    expect(lastRequest?.url).toBe('/audits/42')
  })
})

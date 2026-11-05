import axios, { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, expect, it, vi } from 'vitest'
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), warning: vi.fn() } }))
let last: InternalAxiosRequestConfig | null = null
axios.defaults.adapter = async config => { last = config; return { status: 200, statusText: 'OK', data: { items: [{ id: 8, label: '可见选项' }], total: 1, page: 2, page_size: 20 }, headers: {}, config } }
const { listFilterOptions } = await import('./filterOptions')
beforeEach(() => { last = null; localStorage.clear() })
it.each([
  ['requirement-version', '/requirements/filter-options/versions'],
  ['participant', '/requirements/filter-options/participants'],
  ['owner', '/versions/filter-options/owners'],
] as const)('loads %s options from the parent-scoped endpoint with pagination and selected ID', async (kind, path) => {
  const result = await listFilterOptions(kind, '  搜索  ', 2, 8)
  expect(last?.url).toBe(path)
  expect(last?.method).toBe('get')
  expect(last?.params).toEqual({ keyword: '搜索', page: 2, page_size: 20, selected_id: 8 })
  expect(result.items).toEqual([{ id: 8, label: '可见选项' }])
})
it('bounds remote search text to the endpoint limit and omits an empty query', async () => {
  await listFilterOptions('owner', '字'.repeat(101))
  expect(last?.params.keyword).toHaveLength(100)
  await listFilterOptions('owner', '   ')
  expect(last?.params.keyword).toBeUndefined()
})

import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({ list: vi.fn(), push: vi.fn(), mobile: false, version: false }))
vi.mock('@/api/releases', () => ({ listReleases: mocks.list }))
const route = reactive({ query: {} as Record<string, string> })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: mocks.mobile }) }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => mocks.version }) }))
import ReleaseListView from './ReleaseListView.vue'

beforeEach(() => {
  vi.clearAllMocks()
  route.query = {}
  mocks.push.mockImplementation(async (target: { query?: Record<string, string> } | string) => { if (typeof target !== 'string') route.query = target.query ?? {} })
  mocks.list.mockResolvedValue({ total: 1, page: 1, page_size: 20, items: [{ id: 123, version_id: 456, released_at: '2026-10-01T00:00:00Z', result: 'SUCCESS', release_notes: '发布说明' }] })
})

describe('release list entries', () => {
  it.each([[false, false], [false, true], [true, false], [true, true]])('mobile=%s version permission=%s', async (mobile, version) => {
    mocks.mobile = mobile
    mocks.version = version
    const wrapper = mount(ReleaseListView, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    const buttons = wrapper.findAll('button')
    const detail = buttons.find(button => button.text() === '查看详情')!
    expect(detail).toBeDefined()
    await detail.trigger('click')
    expect(mocks.push).toHaveBeenCalledWith('/releases/123?return_to=%2Freleases')
    const versionButton = buttons.find(button => button.text() === '查看版本')
    expect(!!versionButton).toBe(version)
    if (versionButton) {
      await versionButton.trigger('click')
      expect(mocks.push).toHaveBeenCalledWith('/versions/456?return_to=%2Freleases')
    }
    wrapper.unmount()
  })
})

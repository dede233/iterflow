import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import type { EntityActivity } from '@/types/domain'
const mocks = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('@/api/entityActivities', () => ({ listEntityActivities: mocks.list }))
import RecentEntityActivity from './RecentEntityActivity.vue'

const row = (id: number): EntityActivity => ({ id, action: 'CONFIRM', operator: { id: 1, username: 'tester', display_name: '测试操作人' }, created_at: '2026-11-06T02:00:00Z' })
const mountCard = () => mount(RecentEntityActivity, { props: { id: 7, kind: 'requirement', revision: 1 }, global: { stubs: { 'el-button': { template: '<button><slot/></button>' } } } })
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.requirement.view'] } as any
  useAuthStore().accessToken = 'local-test'
  mocks.list.mockResolvedValue([row(1)])
})
it('shows the latest operator and keeps at most ten descending records collapsed until requested', async () => {
  mocks.list.mockResolvedValue(Array.from({ length: 12 }, (_, i) => row(12-i)))
  const wrapper = mountCard(); await flushPromises()
  expect(wrapper.text()).toContain('测试操作人')
  expect(wrapper.text()).toContain('确认当前需求内容')
  expect(wrapper.find('ol').exists()).toBe(false)
  await wrapper.get('button').trigger('click')
  expect(wrapper.findAll('li')).toHaveLength(10)
  expect(wrapper.get('button').attributes('aria-expanded')).toBe('true')
  await wrapper.get('button').trigger('click')
  expect(wrapper.find('ol').exists()).toBe(false)
  wrapper.unmount()
})
it('refreshes on revision and comment or attachment refresh without exposing stale object data', async () => {
  const wrapper = mountCard(); await flushPromises()
  await wrapper.setProps({ revision: 2 }); await flushPromises()
  await wrapper.setProps({ refreshKey: 1 }); await flushPromises()
  expect(mocks.list).toHaveBeenCalledTimes(3)
  mocks.list.mockResolvedValue([])
  await wrapper.setProps({ id: 8 }); await flushPromises()
  expect(wrapper.text()).toContain('暂无操作记录')
  expect(wrapper.text()).not.toContain('测试操作人')
  wrapper.unmount()
})
it('clears on permission loss and ignores late responses after account changes', async () => {
  let resolve!: (v: EntityActivity[]) => void
  mocks.list.mockImplementationOnce(() => new Promise(r => { resolve = r }))
  const wrapper = mountCard()
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  await flushPromises(); resolve([row(1)]); await flushPromises()
  expect(wrapper.text()).not.toContain('测试操作人')
  expect(mocks.list).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it('reports load failure separately and allows retry; unknown actors remain explicit', async () => {
  mocks.list.mockRejectedValueOnce(new Error('network'))
  const wrapper = mountCard(); await flushPromises()
  expect(wrapper.text()).toContain('暂时无法加载')
  mocks.list.mockResolvedValue([{ ...row(1), operator: null }])
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('系统操作 / 操作人未记录')
  wrapper.unmount()
})

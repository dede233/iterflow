import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), push: vi.fn() }))
vi.mock('@/api/client', () => ({ api: mocks }))
const route = reactive({ path: '/notifications' })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: mocks.push }) }))
import MailSetupNotice from './MailSetupNotice.vue'

const preferences = { revision: 3, mode: 'TASKS', email: null, verified: false, smtp_enabled: true, pending_email: null, notice_acknowledged: false }
const wrappers: ReturnType<typeof mount>[] = []
function render() {
  const wrapper = mount(MailSetupNotice, { global: { stubs: {
    'el-dialog': { props: ['modelValue'], template: '<section v-if="modelValue"><slot/><slot name="footer"/></section>' },
    'el-button': { props: ['loading', 'disabled'], template: '<button :disabled="loading || disabled"><slot/></button>' },
  } } })
  wrappers.push(wrapper)
  return wrapper
}
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia()); route.path = '/notifications'
  useAuthStore().$patch({ accessToken: 'test', user: { id: 1, permission_codes: [] } as any })
  mocks.get.mockResolvedValue({ data: { ...preferences } })
})
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()) })

it.each([
  [{}, '还没有绑定'],
  [{ email: 'a@example.test' }, '尚未完成验证'],
  [{ pending_email: 'a@example.test' }, '尚未完成验证'],
])('explains why setup is needed: %o', async (overrides, text) => {
  mocks.get.mockResolvedValue({ data: { ...preferences, ...overrides } })
  const wrapper = render(); await flushPromises()
  expect(wrapper.text()).toContain(text)
})
it.each([{ verified: true }, { mode: 'OFF' }, { smtp_enabled: false }, { notice_acknowledged: true }, { notice_acknowledged: undefined }])('does not prompt for %o', async overrides => {
  mocks.get.mockResolvedValue({ data: { ...preferences, ...overrides } })
  const wrapper = render(); await flushPromises()
  expect(wrapper.find('button').exists()).toBe(false)
})
it('saves acknowledgement using the current revision and respects server state on remount', async () => {
  mocks.post.mockResolvedValue({ data: { ...preferences, revision: 4, notice_acknowledged: true } })
  const wrapper = render(); await flushPromises()
  await wrapper.findAll('button')[0]!.trigger('click'); await flushPromises()
  expect(mocks.post).toHaveBeenCalledWith('/me/mail-notice/acknowledge', { revision: 3 }, { skipConflictAlert: true })
  expect(wrapper.find('button').exists()).toBe(false)
  mocks.get.mockResolvedValue({ data: { ...preferences, notice_acknowledged: true } })
  const next = render(); await flushPromises()
  expect(next.find('button').exists()).toBe(false)
})
it('retains the notice on save failure and reloads CAS conflicts without replaying writes', async () => {
  mocks.post.mockRejectedValueOnce(new Error('offline')).mockRejectedValueOnce({ response: { status: 409 } })
  const wrapper = render(); await flushPromises()
  await wrapper.findAll('button')[0]!.trigger('click'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('未能保存')
  mocks.get.mockResolvedValue({ data: { ...preferences, revision: 8 } })
  await wrapper.findAll('button')[0]!.trigger('click'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('重新点击')
  expect(mocks.post).toHaveBeenCalledTimes(2)
  mocks.post.mockResolvedValue({ data: { ...preferences, revision: 9, notice_acknowledged: true } })
  await wrapper.findAll('button')[0]!.trigger('click'); await flushPromises()
  expect(mocks.post.mock.calls[2]![1]).toEqual({ revision: 8 })
})
it('opens personal mail settings without acknowledging or sending mail', async () => {
  const wrapper = render(); await flushPromises()
  await wrapper.findAll('button')[1]!.trigger('click'); await flushPromises()
  expect(mocks.push).toHaveBeenCalledWith('/profile#mail-notifications')
  expect(mocks.post).not.toHaveBeenCalled()
  expect(wrapper.find('button').exists()).toBe(false)
})
it('does not interrupt profile settings and reloads state when leaving them', async () => {
  route.path = '/profile'
  const wrapper = render(); await flushPromises()
  expect(mocks.get).not.toHaveBeenCalled()
  route.path = '/notifications'; await flushPromises()
  expect(wrapper.text()).toContain('还没有绑定')
})
it('ignores old account responses and resets dismissal for a different account', async () => {
  let resolve!: (value: unknown) => void
  mocks.get.mockImplementationOnce(() => new Promise(r => { resolve = r }))
  const wrapper = render(); await flushPromises()
  useAuthStore().user = { id: 2, permission_codes: [] } as any; await flushPromises()
  resolve({ data: { ...preferences, verified: true } }); await flushPromises()
  expect(wrapper.text()).toContain('还没有绑定')
  await wrapper.findAll('button')[1]!.trigger('click'); await flushPromises()
  useAuthStore().user = { id: 3, permission_codes: [] } as any; await flushPromises()
  expect(wrapper.text()).toContain('还没有绑定')
  useAuthStore().user = null; await flushPromises()
  expect(wrapper.find('button').exists()).toBe(false)
})
it('does not show a misleading unbound notice when the read fails', async () => {
  mocks.get.mockRejectedValue(new Error('offline'))
  const wrapper = render(); await flushPromises()
  expect(wrapper.find('button').exists()).toBe(false)
})

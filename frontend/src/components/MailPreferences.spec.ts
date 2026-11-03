import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('@/api/client', () => ({ api: mocks }))
import MailPreferences from './MailPreferences.vue'
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: [] } as any
  mocks.get.mockResolvedValue({ data: { revision: 3, mode: 'TASKS', email: 'user@example.test', verified: false, smtp_enabled: false, pending_email: null } })
})
it('explains opt-in verification and retains settings on revision conflict', async () => {
  mocks.put.mockRejectedValue({ response: { status: 409 } })
  const wrapper = mount(MailPreferences, { global: { stubs: {
    SectionCard: { template: '<section><slot/></section>' },
    'el-alert': { props: ['title'], template: '<p>{{ title }}</p>' },
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { template: '<div><slot/></div>' },
    'el-button': { template: '<button><slot/></button>' }, 'el-select': true, 'el-option': true, 'el-input': true,
  } } })
  await flushPromises()
  expect(wrapper.text()).toContain('未验证，不发送进度邮件')
  expect(wrapper.text()).toContain('邮件服务尚未启用')
  await wrapper.findAll('button').find(b => b.text() === '保存偏好')!.trigger('click'); await flushPromises()
  expect(mocks.put).toHaveBeenCalledExactlyOnceWith('/me/mail-preferences', { revision: 3, mode: 'TASKS' })
  useAuthStore().user = null; await flushPromises()
  expect(wrapper.text()).not.toContain('user@example.test')
  wrapper.unmount()
})

const preferences = { revision: 5, mode: 'ALL', email: 'old@example.test', verified: true, smtp_enabled: true, pending_email: 'pending@example.test', notice_acknowledged: true }
function unbindWrapper(overrides = {}) {
  mocks.get.mockResolvedValue({ data: { ...preferences, ...overrides } })
  vi.spyOn(useAuthStore(), 'loadCurrentUser').mockResolvedValue({ id: 1, email: null } as any)
  return mount(MailPreferences, { global: { stubs: {
    SectionCard: { template: '<section><slot/></section>' },
    'el-alert': { props: ['title'], template: '<p role="alert">{{ title }}</p>' },
    'el-dialog': { props: ['modelValue'], template: '<aside v-if="modelValue"><slot/><slot name="footer"/></aside>' },
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { template: '<div><slot/></div>' },
    'el-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot/></button>' },
    'el-select': true, 'el-option': true, 'el-input': { props: ['modelValue'], template: '<input :value="modelValue" />' },
  } } })
}
const click = async (wrapper: ReturnType<typeof unbindWrapper>, text: string) => {
  await wrapper.findAll('button').find(button => button.text() === text)!.trigger('click')
  await flushPromises()
}
it('asks for explicit confirmation and cancel never writes', async () => {
  const wrapper = unbindWrapper(); await flushPromises()
  await click(wrapper, '取消绑定')
  expect(wrapper.text()).toContain('未完成的验证码也会失效')
  expect(mocks.post).not.toHaveBeenCalled()
  await click(wrapper, '暂不取消')
  expect(wrapper.find('aside').exists()).toBe(false)
  expect(mocks.post).not.toHaveBeenCalled(); wrapper.unmount()
})
it('clears binding inputs and refreshes profile after successful unbind', async () => {
  mocks.post.mockResolvedValue({ data: { ...preferences, revision: 6, email: null, verified: false, pending_email: null } })
  const wrapper = unbindWrapper(); await flushPromises()
  await click(wrapper, '取消绑定'); await click(wrapper, '确认取消绑定')
  expect(mocks.post).toHaveBeenCalledExactlyOnceWith('/me/email-unbind', { revision: 5 }, { skipConflictAlert: true })
  expect(wrapper.text()).toContain('通知邮箱已取消绑定')
  expect(wrapper.text()).not.toContain('old@example.test')
  expect(wrapper.text()).not.toContain('pending@example.test')
  expect(wrapper.findAll('input').every(input => input.element.value === '')).toBe(true)
  expect(useAuthStore().loadCurrentUser).toHaveBeenCalledOnce()
  expect(wrapper.find('aside').exists()).toBe(false); wrapper.unmount()
})
it('keeps confirmation on conflict and requires refresh without automatic replay', async () => {
  mocks.post.mockRejectedValue({ response: { status: 409, data: { message: '邮件设置已修改, 请刷新' } } })
  const wrapper = unbindWrapper(); await flushPromises()
  await click(wrapper, '取消绑定'); await click(wrapper, '确认取消绑定')
  expect(wrapper.text()).toContain('邮件设置已修改, 请刷新')
  expect(wrapper.text()).toContain('old@example.test')
  expect(wrapper.findAll('button').some(b => b.text() === '确认取消绑定')).toBe(false)
  await click(wrapper, '刷新设置')
  expect(mocks.get).toHaveBeenCalledTimes(2)
  expect(mocks.post).toHaveBeenCalledTimes(1); wrapper.unmount()
})
it('supports clearing only a pending address and hides unbind when no address exists', async () => {
  const wrapper = unbindWrapper({ email: null, verified: false }); await flushPromises()
  expect(wrapper.findAll('button').some(b => b.text() === '取消绑定')).toBe(true)
  wrapper.unmount()
  const empty = unbindWrapper({ email: null, pending_email: null, verified: false }); await flushPromises()
  expect(empty.findAll('button').some(b => b.text() === '取消绑定')).toBe(false); empty.unmount()
})
it('does not apply an unbind response to a different signed-in account', async () => {
  let resolve!: (value: unknown) => void
  mocks.post.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = unbindWrapper(); await flushPromises(); await click(wrapper, '取消绑定')
  await wrapper.findAll('button').find(b => b.text() === '确认取消绑定')!.trigger('click')
  useAuthStore().user = { id: 2, permission_codes: [] } as any; await flushPromises()
  resolve({ data: { ...preferences, email: null, pending_email: null, verified: false } }); await flushPromises()
  expect(wrapper.text()).not.toContain('通知邮箱已取消绑定')
  expect(useAuthStore().loadCurrentUser).not.toHaveBeenCalled(); wrapper.unmount()
})

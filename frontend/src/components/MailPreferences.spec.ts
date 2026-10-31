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

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn() }))
vi.mock('@/api/collaboration', () => ({ getFeedbackCollaboration: mocks.get, getParticipants: mocks.get, setRecipients: mocks.save, setParticipants: mocks.save, transferFeedback: mocks.save, listPeople: vi.fn() }))
import CollaborationPeople from './CollaborationPeople.vue'
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.feedback.view'] } as any
  mocks.get.mockResolvedValue({ revision: 7, recipients: [{ id: 2, display_name: '接收人员' }], handler_id: null, accepted_by: null, accepted_at: null })
})
function panel() {
  return mount(CollaborationPeople, { props: { id: 1, revision: 7, kind: 'feedback', editable: true }, global: { stubs: {
    SectionCard: { template: '<section><slot/></section>' },
    PeopleSelector: { template: '<div />' },
    'el-form': { template: '<form><slot/></form>' },
    'el-form-item': { template: '<div><slot/></div>' },
    'el-button': { template: '<button><slot/></button>' },
  } } })
}
it('submits the revision from the displayed collaboration state', async () => {
  const wrapper = panel(); await flushPromises()
  expect(wrapper.text()).toContain('接收人员')
  await wrapper.findAll('button').find(b => b.text() === '调整人员')!.trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '保存人员')!.trigger('click')
  await flushPromises()
  expect(mocks.save).toHaveBeenCalledWith(1, 7, [2])
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('does not overwrite a conflict or automatically replay with a new revision', async () => {
  mocks.save.mockRejectedValue({ response: { status: 409 } })
  const wrapper = panel(); await flushPromises()
  await wrapper.findAll('button').find(b => b.text() === '调整人员')!.trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '保存人员')!.trigger('click')
  await flushPromises()
  expect(mocks.save).toHaveBeenCalledTimes(1)
  expect(mocks.get).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('updated')).toBeUndefined()
  wrapper.unmount()
})
it('clears old people and rejects a late response after account changes', async () => {
  let resolve!: (value: any) => void
  mocks.get.mockImplementation(() => new Promise(r => { resolve = r }))
  const wrapper = panel()
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  resolve({ revision: 7, recipients: [{ id: 2, display_name: '旧账号数据' }] })
  await flushPromises()
  expect(wrapper.text()).not.toContain('旧账号数据')
  expect(wrapper.find('form').exists()).toBe(false)
  wrapper.unmount()
})

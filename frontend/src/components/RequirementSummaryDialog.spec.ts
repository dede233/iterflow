import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import type { Requirement } from '@/types/domain'
const mocks = vi.hoisted(() => ({ get: vi.fn(), feedbacks: vi.fn() }))
vi.mock('@/api/entityActivities', () => ({ listEntityActivities: vi.fn().mockResolvedValue([]) }))
vi.mock('@/api/requirements', () => ({ getRequirement: mocks.get, listRequirementFeedbacks: mocks.feedbacks }))
import RequirementSummaryDialog from './RequirementSummaryDialog.vue'

const record = (id: number) => ({ id, requirement_no: `REQ-${id}`, title: `需求${id}`, description: '重要信息', status: 'DONE', priority: 'P2', source: 'DIRECT', requirement_type: 'FEATURE' }) as Requirement
beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = { id: 1, permission_codes: ['rd.requirement.view'] } as any
  auth.accessToken = 'test-account'
  mocks.get.mockImplementation(async id => record(id))
  mocks.feedbacks.mockResolvedValue([])
})
function dialog() {
  return mount(RequirementSummaryDialog, {
    props: { id: 7, returnTo: '/versions?page=2' },
    global: { stubs: {
      'el-dialog': { template: '<div><slot/><slot name="footer"/></div>' },
      'el-button': { template: '<button><slot/></button>' },
      'el-descriptions': { template: '<dl><slot/></dl>' },
      'el-descriptions-item': { template: '<dd><slot/></dd>' },
      RouterLink: { props: ['to'], template: '<a :href="to"><slot/></a>' },
    } },
  })
}
it('loads protected details without fetching unauthorized source feedbacks', async () => {
  const wrapper = dialog(); await flushPromises()
  expect(wrapper.text()).toContain('需求7')
  expect(wrapper.text()).toContain('重要信息')
  expect(mocks.feedbacks).not.toHaveBeenCalled()
  expect(wrapper.get('a').attributes('href')).toContain('/requirements/7')
  wrapper.unmount()
})
it('clears metadata immediately on permission revocation', async () => {
  const wrapper = dialog(); await flushPromises()
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  await flushPromises()
  expect(wrapper.text()).not.toContain('重要信息')
  expect(wrapper.find('a').exists()).toBe(false)
  expect(mocks.get).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it('ignores late responses after switching objects or closing', async () => {
  let resolve!: (value: Requirement) => void
  mocks.get.mockImplementationOnce(() => new Promise<Requirement>(r => { resolve = r }))
  const wrapper = dialog()
  await wrapper.setProps({ id: 8 }); await flushPromises()
  resolve(record(7)); await flushPromises()
  expect(wrapper.text()).toContain('需求8')
  expect(wrapper.text()).not.toContain('需求7')
  await wrapper.setProps({ id: null })
  expect(wrapper.text()).not.toContain('重要信息')
  wrapper.unmount()
})
it.each([403, 404, 500])('isolates read failure %s and permits retry', async status => {
  mocks.get.mockRejectedValueOnce({ response: { status } })
  const wrapper = dialog(); await flushPromises()
  expect(wrapper.text()).toContain('暂时无法查看')
  expect(wrapper.find('a').exists()).toBe(false)
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('需求7')
  wrapper.unmount()
})
it('source feedback failure does not hide the requirement', async () => {
  useAuthStore().user!.permission_codes.push('rd.feedback.view')
  mocks.feedbacks.mockRejectedValue(new Error('unavailable'))
  const wrapper = dialog(); await flushPromises()
  expect(wrapper.text()).toContain('需求7')
  expect(wrapper.text()).toContain('来源反馈暂时无法加载')
  wrapper.unmount()
})

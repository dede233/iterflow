import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn() }))
vi.mock('@/api/collaboration', () => ({ getParticipants: mocks.get, setParticipants: mocks.save }))
import RequirementPeopleDialog from './RequirementPeopleDialog.vue'
import PeopleSelector from './PeopleSelector.vue'
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.requirement.view', 'rd.requirement.edit'] } as any
  mocks.get.mockResolvedValue({ revision: 12, participants: [
    { role: 'CONFIRM', user_id: 1, display_name: '确认人', active: true },
    { role: 'DEVELOP', user_id: 2, display_name: '开发人', active: true },
    { role: 'ACCEPT', user_id: 3, display_name: '验收人', active: true },
  ] })
})
function panel() {
  return mount(RequirementPeopleDialog, { props: { id: 1, roles: ['DESIGN', 'DEVELOP', 'ACCEPT'], title: '安排人员' }, global: { stubs: {
    PeopleSelector: { props: ['modelValue', 'multiple'], template: '<div />' },
    'el-dialog': { template: '<section><slot/></section>' },
    'el-form': { template: '<form><slot/></form>' },
    'el-form-item': { template: '<div><slot/></div>' },
    'el-button': { template: '<button><slot/></button>' },
  } } })
}
it('saves using the fetched revision and preserves confirmation when arranging later roles', async () => {
  const wrapper = panel(); await flushPromises()
  const selectors = wrapper.findAllComponents(PeopleSelector)
  expect(selectors.map(s => s.props('multiple'))).toEqual([true, true, true])
  selectors[0]!.vm.$emit('update:modelValue', [4])
  selectors[1]!.vm.$emit('update:modelValue', [2, 5])
  selectors[2]!.vm.$emit('update:modelValue', [6, 7])
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(1, 12, [
    { role: 'CONFIRM', user_id: 1 }, { role: 'DESIGN', user_id: 4 },
    { role: 'DEVELOP', user_id: 2 }, { role: 'DEVELOP', user_id: 5 }, { role: 'ACCEPT', user_id: 6 }, { role: 'ACCEPT', user_id: 7 },
  ])
  expect(wrapper.emitted('updated')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount()
})
it('retains choices after a conflict and never automatically replays the write', async () => {
  mocks.save.mockRejectedValue({ response: { status: 409 } })
  const wrapper = panel(); await flushPromises()
  wrapper.findAllComponents(PeopleSelector)[1]!.vm.$emit('update:modelValue', [5])
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.get).toHaveBeenCalledTimes(1)
  expect(mocks.save).toHaveBeenCalledTimes(1)
  expect(wrapper.findAllComponents(PeopleSelector)[1]!.props('modelValue')).toEqual([5])
  expect(wrapper.emitted('close')).toBeUndefined()
  expect(wrapper.get('[role="alert"]').text()).toContain('所选人员已保留')
  wrapper.unmount()
})
it('preserves other roles when only the acceptance person is edited', async () => {
  const wrapper = panel(); await wrapper.setProps({ roles: ['ACCEPT'] }); await flushPromises()
  wrapper.findComponent(PeopleSelector).vm.$emit('update:modelValue', [7])
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(1, 12, [
    { role: 'CONFIRM', user_id: 1 }, { role: 'DEVELOP', user_id: 2 }, { role: 'ACCEPT', user_id: 7 },
  ])
  wrapper.unmount()
})
it('ignores a late personnel response after losing permission', async () => {
  let resolve!: (value: unknown) => void
  mocks.get.mockImplementation(() => new Promise(r => { resolve = r }))
  const wrapper = panel()
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  resolve({ revision: 12, participants: [{ role: 'CONFIRM', user_id: 1, display_name: '旧人员', active: true }] })
  await flushPromises()
  expect(wrapper.find('form').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('旧人员')
  expect(mocks.save).not.toHaveBeenCalled()
  wrapper.unmount()
})

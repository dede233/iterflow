import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ batch: vi.fn(), requirement: vi.fn(), workflow: vi.fn(), people: vi.fn(), feedback: vi.fn(), collaboration: vi.fn() }))
vi.mock('@/api/entityActions', () => ({ batchActions: mocks.batch }))
vi.mock('@/api/requirements', () => ({ getRequirement: mocks.requirement }))
vi.mock('@/api/feedbacks', () => ({ getFeedback: mocks.feedback }))
vi.mock('@/api/collaboration', () => ({ getWorkflow: mocks.workflow, getParticipants: mocks.people, getFeedbackCollaboration: mocks.collaboration }))
import BatchActionsDialog from './BatchActionsDialog.vue'
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.requirement.status', 'rd.requirement.view', 'rd.feedback.edit'] } as any
  mocks.requirement.mockImplementation(id => Promise.resolve({ id, status: id === 2 ? 'ONLINE' : 'DRAFT', revision: 7 }))
  mocks.workflow.mockResolvedValue({ revision: 7, needs_confirmation: true, design_status: 'NOT_REQUIRED' })
  mocks.people.mockResolvedValue({ revision: 7, participants: [{ user_id: 1, role: 'CONFIRM', active: true }] })
  mocks.batch.mockResolvedValue({ results: [{ id: 1, success: true, status_code: 200, code: 0, message: '已完成', revision: 8 }] })
})
function panel() {
  return mount(BatchActionsDialog, { props: { kind: 'requirements', rows: [{ id: 1, title: '待确认需求' }, { id: 2, title: '已上线需求' }] }, global: { stubs: {
    'el-dialog': { props: ['modelValue'], template: '<section v-if="modelValue"><slot/><slot name="footer"/></section>' },
    'el-button': { props: ['disabled', 'loading'], template: '<button :disabled="disabled || loading"><slot/></button>' },
    'el-select': { props: ['modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot/></select>' },
    'el-option': { props: ['value', 'label'], template: '<option :value="value">{{ label }}</option>' },
    'el-checkbox-group': { name: 'el-checkbox-group', props: ['modelValue'], template: '<div data-select><slot/></div>' },
    'el-checkbox': { template: '<label><slot/></label>' },
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { template: '<div><slot/></div>' },
    'el-input': { props: ['modelValue'], template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  } } })
}
async function click(wrapper: ReturnType<typeof panel>, text: string) { await wrapper.findAll('button').find(b => b.text().includes(text))!.trigger('click'); await flushPromises() }
async function prepare(wrapper: ReturnType<typeof panel>) {
  await click(wrapper, '批量操作')
  wrapper.findComponent({ name: 'el-checkbox-group' }).vm.$emit('update:modelValue', [1, 2])
  await flushPromises(); await click(wrapper, '检查所选记录')
}
it('previews mixed states and only submits eligible rows with the inspected revision', async () => {
  const wrapper = panel(); await prepare(wrapper)
  expect(wrapper.text()).toContain('当前阶段不支持此操作')
  await click(wrapper, '执行可操作的 1 项')
  expect(mocks.batch).toHaveBeenCalledExactlyOnceWith('requirements', { action: 'CONFIRM', items: [{ id: 1, revision: 7 }], reason: null })
  expect(wrapper.text()).toContain('成功'); expect(wrapper.emitted('updated')).toHaveLength(1)
  expect(wrapper.findAll('button').some(b => b.text().includes('执行可操作'))).toBe(false)
  wrapper.unmount()
})
it('requires delegated reasons and keeps partial conflicts visible without replay', async () => {
  useAuthStore().user!.can_view_api_docs = true
  mocks.people.mockResolvedValue({ revision: 7, participants: [{ user_id: 3, role: 'CONFIRM', active: true }] })
  mocks.batch.mockResolvedValue({ results: [{ id: 1, success: false, status_code: 409, code: 40910, message: '信息已更新', revision: 9 }] })
  const wrapper = panel(); await prepare(wrapper); await click(wrapper, '执行可操作')
  expect(mocks.batch).not.toHaveBeenCalled(); expect(wrapper.text()).toContain('至少 2 个字符')
  await wrapper.get('textarea').setValue('代为处理'); await click(wrapper, '执行可操作')
  expect(wrapper.text()).toContain('信息已更新'); expect(mocks.batch).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it('discards a preflight response after switching accounts', async () => {
  let resolve!: (value: unknown) => void
  mocks.requirement.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel(); await click(wrapper, '批量操作')
  wrapper.findComponent({ name: 'el-checkbox-group' }).vm.$emit('update:modelValue', [1]); await flushPromises()
  await click(wrapper, '检查所选记录')
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  resolve({ id: 1, status: 'DRAFT', revision: 7 }); await flushPromises()
  expect(wrapper.find('section').exists()).toBe(false); expect(mocks.batch).not.toHaveBeenCalled(); wrapper.unmount()
})

const contextChanges = [
  { label: 'the list contains different objects', props: { rows: [{ id: 3, title: '另一页需求' }] } },
  { label: 'the entity kind changes', props: { kind: 'feedbacks' as const } },
]
it.each(contextChanges)('invalidates a completed preflight when $label', async ({ props }) => {
  const wrapper = panel(); await prepare(wrapper)
  expect(wrapper.findAll('button').some(b => b.text().includes('执行可操作的 1 项'))).toBe(true)
  await wrapper.setProps(props); await flushPromises()
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => b.text().includes('执行可操作'))).toBe(false)
  expect(wrapper.findAll('button').find(b => b.text().includes('检查所选记录'))!.attributes('disabled')).toBeDefined()
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([])
  expect(mocks.batch).not.toHaveBeenCalled(); wrapper.unmount()
})
it.each(contextChanges)('discards a pending preflight when $label', async ({ props }) => {
  let resolve!: (value: unknown) => void
  mocks.requirement.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel(); await click(wrapper, '批量操作')
  wrapper.findComponent({ name: 'el-checkbox-group' }).vm.$emit('update:modelValue', [1]); await flushPromises()
  await click(wrapper, '检查所选记录')
  expect(mocks.requirement).toHaveBeenCalledExactlyOnceWith(1)
  await wrapper.setProps(props); await flushPromises()
  resolve({ id: 1, status: 'DRAFT', revision: 7 }); await flushPromises()
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => b.text().includes('执行可操作'))).toBe(false)
  expect(wrapper.findAll('button').find(b => b.text().includes('检查所选记录'))!.attributes('disabled')).toBeDefined()
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([])
  expect(mocks.batch).not.toHaveBeenCalled(); wrapper.unmount()
})

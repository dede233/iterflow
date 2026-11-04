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

type Row = { id: number; title: string; requirement_no?: string; feedback_no?: string; status?: string }
const initialRows: Row[] = [
  { id: 1, title: '待确认需求', requirement_no: 'REQ-101', status: 'DRAFT' },
  { id: 2, title: '已上线需求', requirement_no: 'REQ-102', status: 'ONLINE' },
]
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['rd.requirement.status', 'rd.requirement.view', 'rd.feedback.edit', 'rd.feedback.view'] } as any
  mocks.requirement.mockImplementation(id => Promise.resolve({ id, title: id === 2 ? '已上线需求' : '待确认需求', requirement_no: `REQ-${100 + id}`, status: id === 2 ? 'ONLINE' : 'DRAFT', revision: 7 }))
  mocks.workflow.mockResolvedValue({ revision: 7, needs_confirmation: true, design_status: 'NOT_REQUIRED' })
  mocks.people.mockResolvedValue({ revision: 7, participants: [{ user_id: 1, role: 'CONFIRM', active: true }] })
  mocks.feedback.mockImplementation(id => Promise.resolve({ id, title: '待处理反馈', feedback_no: `FB-${id}`, status: 'NEW', revision: 7 }))
  mocks.collaboration.mockResolvedValue({ revision: 7, recipients: [{ id: 1, display_name: '接收人' }] })
  mocks.batch.mockResolvedValue({ results: [{ id: 1, success: true, status_code: 200, code: 0, message: '已完成', revision: 8 }] })
})
function panel(props: { kind?: 'requirements' | 'feedbacks'; rows?: Row[]; scope?: 'current-page' | 'version-list' } = {}) {
  return mount(BatchActionsDialog, { props: { kind: 'requirements', rows: initialRows, ...props }, global: { stubs: {
    'el-dialog': { props: ['modelValue'], template: '<section v-if="modelValue"><slot/><slot name="footer"/></section>' },
    'el-button': { props: ['disabled', 'loading'], template: '<button :disabled="disabled || loading"><slot/></button>' },
    'el-checkbox-group': { name: 'el-checkbox-group', props: ['modelValue', 'max', 'disabled'], template: '<div data-select><slot/></div>' },
    'el-checkbox': { template: '<label><slot/></label>' },
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { props: ['label'], template: '<div>{{ label }}<slot/></div>' },
    'el-input': { props: ['modelValue', 'disabled'], template: '<textarea :disabled="disabled" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
    'el-tag': { template: '<span><slot/></span>' },
  } } })
}
function button(wrapper: ReturnType<typeof panel>, text: string) {
  const found = wrapper.findAll('button').find(b => b.text().includes(text))
  expect(found, `button containing ${text}`).toBeDefined()
  return found!
}
async function click(wrapper: ReturnType<typeof panel>, text: string) { await button(wrapper, text).trigger('click'); await flushPromises() }
async function choose(wrapper: ReturnType<typeof panel>, value = 'CONFIRM') { await wrapper.get(`input[type="radio"][value="${value}"]`).setValue(); await flushPromises() }
async function select(wrapper: ReturnType<typeof panel>, ids: number[]) {
  wrapper.findComponent({ name: 'el-checkbox-group' }).vm.$emit('update:modelValue', ids)
  await flushPromises()
}
async function prepare(wrapper: ReturnType<typeof panel>, ids = [1, 2], action = 'CONFIRM') {
  await click(wrapper, '批量处理'); await choose(wrapper, action); await select(wrapper, ids)
  await click(wrapper, '下一步：检查')
}

it('asks for an explicit action and selection before checking, with scope and record labels', async () => {
  const wrapper = panel(); await click(wrapper, '批量处理需求')
  expect(wrapper.findAll('input[type="radio"]').some(r => (r.element as HTMLInputElement).checked)).toBe(false)
  expect(wrapper.text()).toContain('当前页'); expect(wrapper.text()).toContain('REQ-101')
  expect(wrapper.text()).toContain('待确认'); expect(wrapper.text()).toContain('已上线')
  expect(button(wrapper, '下一步：检查').attributes('disabled')).toBeDefined()
  await select(wrapper, [1])
  expect(button(wrapper, '下一步：检查').attributes('disabled')).toBeDefined()
  await choose(wrapper)
  expect(button(wrapper, '下一步：检查').attributes('disabled')).toBeUndefined()
  expect(mocks.requirement).not.toHaveBeenCalled(); expect(mocks.batch).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('previews mixed states and submits only eligible records with inspected revisions', async () => {
  const wrapper = panel(); await prepare(wrapper)
  const preview = wrapper.get('[aria-label="操作前检查"]')
  expect(preview.text()).toContain('REQ-101'); expect(preview.text()).toContain('将执行')
  expect(preview.text()).toContain('已上线'); expect(preview.text()).toContain('跳过')
  expect(preview.find('a[href*="/requirements/2"]').exists()).toBe(true)
  await click(wrapper, '确认需求（1 条）')
  expect(mocks.batch).toHaveBeenCalledExactlyOnceWith('requirements', { action: 'CONFIRM', items: [{ id: 1, revision: 7 }], reason: null })
  const results = wrapper.get('[aria-label="批量操作结果"]')
  expect(results.text()).toContain('REQ-101'); expect(results.text()).toContain('待确认需求'); expect(results.text()).toContain('成功')
  expect(results.text()).toContain('REQ-102'); expect(results.text()).toContain('跳过')
  expect(wrapper.emitted('updated')).toHaveLength(1)
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => /下一步：检查|确认需求/.test(b.text()))).toBe(false)
  await wrapper.setProps({ rows: [{ id: 5, title: '刷新后的另一条需求' }] }); await flushPromises()
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).toContain('REQ-101')
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).not.toContain('刷新后的另一条需求')
  expect(mocks.batch).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})
it.each([false, true])('keeps submitted identities after a parent refresh during a write (rejected=%s)', async rejected => {
  let resolve!: (value: unknown) => void
  let reject!: (reason: unknown) => void
  mocks.requirement.mockResolvedValue({ id: 1, title: '服务端更新后的标题', requirement_no: 'REQ-101', status: 'DRAFT', revision: 7 })
  mocks.batch.mockReturnValue(new Promise((r, fail) => { resolve = r; reject = fail }))
  const wrapper = panel(); await prepare(wrapper, [1])
  expect(wrapper.get('[aria-label="操作前检查"]').text()).toContain('服务端更新后的标题')
  expect(wrapper.get('[aria-label="操作前检查"]').text()).not.toContain('待确认需求')
  await click(wrapper, '确认需求（1 条）')
  await wrapper.setProps({ rows: [{ id: 5, title: '刷新后的另一条需求' }] }); await flushPromises()
  expect(wrapper.get('[aria-label="操作前检查"]').text()).toContain('服务端更新后的标题')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.batch).toHaveBeenCalledTimes(1)
  if (rejected) reject(new Error('response lost'))
  else resolve({ results: [{ id: 1, success: true, status_code: 200, code: 0, message: '已完成', revision: 8 }] })
  await flushPromises()
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).toContain(rejected ? '待核对' : '成功')
  expect(wrapper.findAll('button').some(b => /确认需求|下一步：检查|返回调整/.test(b.text()))).toBe(false)
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).toContain('REQ-101')
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).toContain('服务端更新后的标题')
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).not.toContain('刷新后的另一条需求')
  expect(wrapper.emitted('updated')).toHaveLength(1)
  expect(mocks.batch).toHaveBeenCalledExactlyOnceWith('requirements', { action: 'CONFIRM', items: [{ id: 1, revision: 7 }], reason: null })
  wrapper.unmount()
})
it('requires delegated reasons and explains partial conflicts without replay', async () => {
  useAuthStore().user!.can_view_api_docs = true
  mocks.people.mockResolvedValue({ revision: 7, participants: [{ user_id: 3, role: 'CONFIRM', active: true }] })
  mocks.batch.mockResolvedValue({ results: [{ id: 1, success: false, status_code: 409, code: 40910, message: '信息已更新', revision: 9 }] })
  const wrapper = panel(); await prepare(wrapper); await click(wrapper, '确认需求（1 条）')
  expect(mocks.batch).not.toHaveBeenCalled(); expect(wrapper.text()).toContain('至少 2 个字符')
  expect(wrapper.text()).toContain('代操作原因')
  await wrapper.get('textarea').setValue('代为处理'); await click(wrapper, '确认需求（1 条）')
  expect(wrapper.get('[aria-label="批量操作结果"]').text()).toContain('失败')
  expect(wrapper.text()).toContain('信息已更新'); expect(mocks.batch).toHaveBeenCalledTimes(1)
  expect(wrapper.findAll('button').some(b => /重新执行|重试/.test(b.text()))).toBe(false)
  wrapper.unmount()
})
it('returns to selection and requires a fresh check instead of using the old revision', async () => {
  const wrapper = panel(); await prepare(wrapper)
  await click(wrapper, '返回调整')
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => b.text().includes('确认需求'))).toBe(false)
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([1, 2])
  mocks.requirement.mockImplementation(id => Promise.resolve({ id, status: id === 2 ? 'ONLINE' : 'DRAFT', revision: 8 }))
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: true, design_status: 'NOT_REQUIRED' })
  mocks.people.mockResolvedValue({ revision: 8, participants: [{ user_id: 1, role: 'CONFIRM', active: true }] })
  await click(wrapper, '下一步：检查'); await click(wrapper, '确认需求（1 条）')
  expect(mocks.batch.mock.calls[0]![1].items).toEqual([{ id: 1, revision: 8 }])
  wrapper.unmount()
})
it('selects at most 50 visible records and lets users clear them without requests', async () => {
  const wrapper = panel({ rows: Array.from({ length: 60 }, (_, i) => ({ id: i + 1, title: `需求${i + 1}` })), scope: 'version-list' })
  await click(wrapper, '批量处理需求')
  expect(wrapper.text()).toContain('版本'); expect(wrapper.text()).toContain('筛选')
  await click(wrapper, '选择前 50 条')
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual(Array.from({ length: 50 }, (_, i) => i + 1))
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('max')).toBe(50)
  await click(wrapper, '清空选择')
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([])
  expect(mocks.requirement).not.toHaveBeenCalled(); expect(mocks.batch).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('disables the entry for an empty page and execution when all selected records are blocked', async () => {
  const empty = panel({ rows: [] })
  expect(button(empty, '批量处理需求').attributes('disabled')).toBeDefined(); empty.unmount()
  const wrapper = panel(); await prepare(wrapper, [2])
  expect(wrapper.get('[aria-label="操作前检查"]').text()).toContain('已上线')
  expect(wrapper.findAll('button').some(b => b.text().includes('确认需求'))).toBe(false)
  expect(wrapper.text()).toContain('没有可执行')
  expect(wrapper.text()).toContain('返回调整'); expect(mocks.batch).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('requires a specific closing reason for feedback and preserves the selected action in the payload', async () => {
  const wrapper = panel({ kind: 'feedbacks', rows: [{ id: 1, title: '待处理反馈', feedback_no: 'FB-1', status: 'NEW' }] })
  await prepare(wrapper, [1], 'CLOSED')
  expect(wrapper.text()).toContain('关闭原因')
  await click(wrapper, '确认关闭反馈（1 条）')
  expect(mocks.batch).not.toHaveBeenCalled()
  await wrapper.get('textarea').setValue('重复提交，已通过其他记录处理')
  await click(wrapper, '确认关闭反馈（1 条）')
  expect(mocks.batch).toHaveBeenCalledExactlyOnceWith('feedbacks', { action: 'CLOSED', items: [{ id: 1, revision: 7 }], reason: '重复提交，已通过其他记录处理' })
  wrapper.unmount()
})
it('keeps an unknown write outcome terminal and asks users to verify instead of retrying', async () => {
  mocks.batch.mockRejectedValue(new Error('connection reset after sending'))
  const wrapper = panel(); await prepare(wrapper, [1]); await click(wrapper, '确认需求（1 条）')
  expect(mocks.batch).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toMatch(/核对|确认实际/)
  expect(wrapper.findAll('button').some(b => /下一步：检查|确认需求|返回调整|重试/.test(b.text()))).toBe(false)
  expect(wrapper.text()).not.toMatch(/全部失败|成功 0.*失败 1/)
  wrapper.unmount()
})
it('discards a preflight response after switching accounts', async () => {
  let resolve!: (value: unknown) => void
  mocks.requirement.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel(); await click(wrapper, '批量处理需求'); await choose(wrapper); await select(wrapper, [1])
  await click(wrapper, '下一步：检查')
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
  expect(button(wrapper, '确认需求（1 条）').exists()).toBe(true)
  await wrapper.setProps(props); await flushPromises()
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => b.text().includes('确认需求'))).toBe(false)
  expect(button(wrapper, '下一步：检查').attributes('disabled')).toBeDefined()
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([])
  expect(mocks.batch).not.toHaveBeenCalled(); wrapper.unmount()
})
it.each(contextChanges)('discards a pending preflight when $label', async ({ props }) => {
  let resolve!: (value: unknown) => void
  mocks.requirement.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel(); await click(wrapper, '批量处理需求'); await choose(wrapper); await select(wrapper, [1])
  await click(wrapper, '下一步：检查')
  expect(mocks.requirement).toHaveBeenCalledExactlyOnceWith(1)
  await wrapper.setProps(props); await flushPromises()
  resolve({ id: 1, status: 'DRAFT', revision: 7 }); await flushPromises()
  expect(wrapper.find('[aria-label="操作前检查"]').exists()).toBe(false)
  expect(wrapper.findAll('button').some(b => b.text().includes('确认需求'))).toBe(false)
  expect(button(wrapper, '下一步：检查').attributes('disabled')).toBeDefined()
  expect(wrapper.findComponent({ name: 'el-checkbox-group' }).props('modelValue')).toEqual([])
  expect(mocks.batch).not.toHaveBeenCalled(); wrapper.unmount()
})

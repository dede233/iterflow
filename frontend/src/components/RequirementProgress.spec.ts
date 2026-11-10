import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ workflow: vi.fn(), participants: vi.fn(), act: vi.fn() }))
vi.mock('@/api/collaboration', () => ({ getWorkflow: mocks.workflow, getParticipants: mocks.participants, actWorkflow: mocks.act }))
import RequirementProgress from './RequirementProgress.vue'
beforeEach(() => {
  vi.resetAllMocks(); setActivePinia(createPinia())
  useAuthStore().user = { id: 2, permission_codes: ['rd.requirement.view', 'rd.requirement.status'] } as any
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: true, legacy_completed: false, design_status: 'NOT_REQUIRED', records: [] })
  mocks.participants.mockResolvedValue({ participants: [{ user_id: 2, role: 'CONFIRM', display_name: '确认人', active: true }] })
})
function panel() {
  return mount(RequirementProgress, { props: { item: { id: 1, revision: 8, status: 'DRAFT' } as any }, global: { stubs: {
    RequirementPeopleDialog: true, SectionCard: { template: '<section><slot/></section>' },
    'el-alert': { props: ['title'], template: '<p>{{ title }}</p>' },
    'el-dialog': { props: ['modelValue'], emits: ['closed'], watch: { modelValue(value: boolean) { if (!value) (this as any).$emit('closed') } }, template: '<div v-if="modelValue"><slot/></div>' },
    'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { props: ['label', 'error'], template: '<div>{{ label }}<slot/><p v-if="error" role="alert">{{ error }}</p></div>' },
    'el-button': { template: '<button><slot/></button>' },
    'el-input': { props: ['modelValue'], emits: ['update:modelValue', 'input'], template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value); $emit(\'input\', $event.target.value)" />' },
  } } })
}
it('shows six steps and uses the displayed revision without replaying conflicts', async () => {
  mocks.act.mockRejectedValue({ response: { status: 409 } })
  const wrapper = panel(); await flushPromises()
  expect(wrapper.find('.progress-toggle').attributes('aria-expanded')).toBe('false')
  expect(wrapper.findAll('li')).toHaveLength(0)
  expect(wrapper.find('.progress-summary').text()).toBe('确认人')
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('li')).toHaveLength(6)
  expect(wrapper.text()).toContain('等待确认当前内容')
  await wrapper.findAll('button').find(b => b.text() === '确认当前内容')!.trigger('click')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).toHaveBeenCalledExactlyOnceWith(1, { action: 'CONFIRM', revision: 8, reason: null })
  expect(wrapper.emitted('updated')).toBeUndefined()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('li')).toHaveLength(0)
  wrapper.unmount()
})
it('clears progress on loss of access and ignores old responses', async () => {
  let resolve!: (value: any) => void
  mocks.workflow.mockImplementation(() => new Promise(r => { resolve = r }))
  const wrapper = panel()
  useAuthStore().user = { id: 3, permission_codes: [] } as any
  resolve({ revision: 8, records: [], design_status: 'DONE' }); await flushPromises()
  expect(wrapper.findAll('li')).toHaveLength(0)
  wrapper.unmount()
})
it('places assignment in the planned card after confirmation and preserves confirmation assignment', async () => {
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.text()).not.toContain('查看 / 调整环节人员')
  expect(wrapper.find('.step-detail').text()).toContain('调整确认人')
  expect(wrapper.find('.step-detail').text()).not.toContain('选择 / 调整人员')
  await wrapper.setProps({ item: { id: 1, revision: 9, status: 'CONFIRMED' } as any }); await flushPromises()
  const card = wrapper.find('.step-detail')
  expect(card.text()).toContain('开发：待分配')
  expect(card.text()).toContain('设计：不需要设计')
  expect(card.text()).toContain('验收：待分配')
  await card.find('button').trigger('click')
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).props('roles')).toEqual(['DESIGN', 'DEVELOP', 'ACCEPT'])
  await wrapper.setProps({ readonly: true })
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).exists()).toBe(false)
  expect(wrapper.findAll('.step-people-button')).toHaveLength(0)
  wrapper.unmount()
})
it.each(['ONLINE', 'CANCELED'])('does not offer personnel edits for terminal %s', async status => {
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 9, status } as any }); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('.step-people-button')).toHaveLength(0)
  wrapper.unmount()
})

it.each([{ participants: [] }, { participants: [{ user_id: 2, role: 'CONFIRM', display_name: '已停用确认人', active: false }] }])('guides administrators to assign an active confirmer before confirming: %j', async ({ participants }) => {
  useAuthStore().user!.can_view_api_docs = true
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  mocks.participants.mockResolvedValue({ revision: 8, participants })
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.text()).toContain('请先在待确认环节设置有效的需求确认人')
  expect(wrapper.findAll('button').some(b => ['确认当前内容', '要求补充说明'].includes(b.text()))).toBe(false)
  await wrapper.findAll('button').find(b => b.text() === '设置确认人')!.trigger('click')
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).props('roles')).toEqual(['CONFIRM'])
  expect(mocks.act).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('explains who can assign when the viewer cannot edit people', async () => {
  mocks.participants.mockResolvedValue({ revision: 8, participants: [] })
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.text()).toContain('请联系有人员编辑权限的成员完成设置')
  expect(wrapper.findAll('.step-people-button')).toHaveLength(0)
  wrapper.unmount()
})

it('requires a reason for delegated confirmation before sending a request', async () => {
  useAuthStore().user!.can_view_api_docs = true
  mocks.participants.mockResolvedValue({ revision: 8, participants: [{ user_id: 3, role: 'CONFIRM', display_name: '其他确认人', active: true }] })
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '确认当前内容')!.trigger('click')
  expect(wrapper.find('form').text()).toContain('代操作原因（必填）')
  await wrapper.find('textarea').setValue('  ')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).not.toHaveBeenCalled()
  expect(wrapper.find('[role="alert"]').text()).toBe('请填写说明后再提交')
  await wrapper.find('textarea').setValue(' 经确认人授权代为确认 ')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).toHaveBeenCalledExactlyOnceWith(1, { action: 'CONFIRM', revision: 8, reason: '经确认人授权代为确认' })
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})

it('does not allow a non-designated ordinary user to confirm', async () => {
  mocks.participants.mockResolvedValue({ participants: [{ user_id: 3, role: 'CONFIRM', display_name: '其他确认人', active: true }] })
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('button').some(b => b.text() === '确认当前内容')).toBe(false)
  wrapper.unmount()
})

it.each(['CONFIRMED', 'DEVELOPING', 'TESTING'])('does not offer delegated role actions without assigned people in %s', async status => {
  useAuthStore().user!.can_view_api_docs = true
  mocks.participants.mockResolvedValue({ participants: [] })
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 8, status } as any }); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('button').some(b => ['开始开发', '提交验收', '验收通过', '启用 / 重新打开设计'].includes(b.text()))).toBe(false)
  wrapper.unmount()
})

it('opens assignment once after successful confirmation and refreshed revision', async () => {
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '确认当前内容')!.trigger('click')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).exists()).toBe(false)
  await wrapper.setProps({ item: { id: 1, revision: 9, status: 'CONFIRMED' } as any }); await flushPromises()
  const dialog = wrapper.findComponent({ name: 'RequirementPeopleDialog' })
  expect(dialog.props('roles')).toEqual(['DESIGN', 'DEVELOP', 'ACCEPT'])
  dialog.vm.$emit('close'); await flushPromises()
  await wrapper.setProps({ item: { id: 1, revision: 10, status: 'CONFIRMED' } as any }); await flushPromises()
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).exists()).toBe(false)
  wrapper.unmount()
})

it.each(['conflict', 'no-edit', 'switch', 'reconfirm'])('does not automatically open assignment for %s', async mode => {
  if (mode !== 'no-edit') useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  if (mode === 'conflict') mocks.act.mockRejectedValue(new Error('conflict'))
  const wrapper = panel(); await flushPromises()
  if (mode === 'reconfirm') {
    await wrapper.setProps({ item: { id: 1, revision: 8, status: 'DEVELOPING' } as any }); await flushPromises()
  }
  await wrapper.find('.progress-toggle').trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '确认当前内容')!.trigger('click')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  await wrapper.setProps({ item: { id: mode === 'switch' ? 2 : 1, revision: 9, status: 'CONFIRMED' } as any }); await flushPromises()
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).exists()).toBe(false)
  wrapper.unmount()
})

it.each(['missing-acceptor', 'unfinished-design', 'unconfirmed-content'])('blocks submission before opening a status form: %s', async mode => {
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: mode === 'unconfirmed-content', design_status: mode === 'unfinished-design' ? 'IN_PROGRESS' : 'NOT_REQUIRED', records: [] })
  mocks.participants.mockResolvedValue({ participants: [
    { user_id: 2, role: 'DEVELOP', active: true },
    ...(mode === 'missing-acceptor' ? [] : [{ user_id: 3, role: 'ACCEPT', active: true }]),
  ] })
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 8, status: 'DEVELOPING' } as any }); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  const button = wrapper.findAll('button').find(b => b.text() === '提交验收')!
  expect(button.attributes('disabled')).toBeDefined()
  await button.trigger('click')
  expect(wrapper.emitted('status')).toBeUndefined()
  expect(mocks.act).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('opens a focused personnel editor with a clear missing-role hint', async () => {
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: false, design_status: 'NOT_REQUIRED', records: [] })
  mocks.participants.mockResolvedValue({ participants: [] })
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 8, status: 'CONFIRMED' } as any }); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.text()).toContain('尚未设置有效的开发人员')
  await wrapper.findAll('button').find(b => b.text() === '设置开发人员')!.trigger('click')
  expect(wrapper.findComponent({ name: 'RequirementPeopleDialog' }).props('roles')).toEqual(['DEVELOP'])
  expect(wrapper.emitted('status')).toBeUndefined()
  wrapper.unmount()
})

it.each([
  ['CONFIRMED', '开始开发', 'DEVELOP'], ['DEVELOPING', '提交验收', 'DEVELOP'],
  ['TESTING', '验收通过', 'ACCEPT'], ['TESTING', '退回开发', 'ACCEPT'],
  ['DONE', '重新开发', 'DEVELOP'], ['PAUSED', '恢复开发', 'DEVELOP'],
])('marks delegated %s / %s as requiring an explicit reason', async (status, label, role) => {
  useAuthStore().user!.can_view_api_docs = true
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: false, design_status: 'NOT_REQUIRED', records: [] })
  mocks.participants.mockResolvedValue({ participants: [
    { user_id: 3, role, active: true }, { user_id: 4, role: 'ACCEPT', active: true },
  ] })
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 8, status } as any }); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  await wrapper.findAll('button').find(b => b.text() === label)!.trigger('click')
  expect(wrapper.emitted('status')?.[0]?.[0]).toMatchObject({ needsReason: true, reasonLabel: '代操作原因（必填）' })
  wrapper.unmount()
})

it('keeps confirmation available while progress is collapsed', async () => {
  const wrapper = panel(); await flushPromises()
  expect(wrapper.findAll('li')).toHaveLength(0)
  await wrapper.findAll('button').find(b => b.text() === '确认当前内容')!.trigger('click')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).toHaveBeenCalledExactlyOnceWith(1, { action: 'CONFIRM', revision: 8, reason: null })
  wrapper.unmount()
})
it('allows any of multiple active confirmers and requires a reason to reopen cancellation', async () => {
  mocks.participants.mockResolvedValue({ participants: [
    { user_id: 3, role: 'CONFIRM', display_name: '第一确认人', active: true },
    { user_id: 2, role: 'CONFIRM', display_name: '第二确认人', active: true },
  ] })
  const wrapper = panel(); await flushPromises()
  expect(wrapper.find('.progress-summary').text()).toContain('第一确认人、第二确认人')
  expect(wrapper.findAll('button').some(b => b.text() === '确认当前内容')).toBe(true)
  await wrapper.setProps({ item: { id: 1, revision: 8, status: 'CANCELED' } as any }); await flushPromises()
  expect(wrapper.findAll('button').some(b => b.text() === '确认当前内容')).toBe(false)
  await wrapper.findAll('button').find(b => b.text() === '重新打开需求')!.trigger('click')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).not.toHaveBeenCalled()
  await wrapper.find('textarea').setValue('恢复这个需求')
  await wrapper.find('form').trigger('submit'); await flushPromises()
  expect(mocks.act).toHaveBeenCalledExactlyOnceWith(1, { action: 'REOPEN', revision: 8, reason: '恢复这个需求' })
  wrapper.unmount()
})
it('keeps collapsed prerequisite guards and removes all write actions online', async () => {
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: false, design_status: 'IN_PROGRESS', records: [] })
  mocks.participants.mockResolvedValue({ participants: [{ user_id: 2, role: 'DEVELOP', active: true }] })
  useAuthStore().user!.permission_codes.push('rd.requirement.edit')
  const wrapper = panel()
  await wrapper.setProps({ item: { id: 1, revision: 8, status: 'DEVELOPING' } as any }); await flushPromises()
  const button = wrapper.findAll('button').find(b => b.text() === '提交验收')!
  expect(button.attributes('disabled')).toBeDefined()
  expect(wrapper.text()).toContain('尚未设置有效的验收人员')
  await button.trigger('click'); expect(wrapper.emitted('status')).toBeUndefined()
  await wrapper.setProps({ item: { id: 1, revision: 8, status: 'ONLINE' } as any }); await flushPromises()
  expect(wrapper.find('.progress-actions').exists()).toBe(false)
  await wrapper.find('.progress-toggle').trigger('click')
  expect(wrapper.findAll('.step-people-button')).toHaveLength(0)
  wrapper.unmount()
})

it('renders explicit rich-text history safely and keeps legacy snapshots literal', async () => {
  mocks.workflow.mockResolvedValue({ revision: 8, needs_confirmation: false, design_status: 'NOT_REQUIRED', records: [
    { id: 'rich', action: 'CONFIRM', actor_id: 2, created_at: '2026-11-04T00:00:00Z', detail: { description: '<p><strong>富文本范围</strong><script>alert(1)</script></p>', description_format: 'HTML' } },
    { id: 'legacy', action: 'CONFIRM', actor_id: 2, created_at: '2026-11-03T00:00:00Z', detail: { description: '<b>旧文本范围</b>' } },
  ] })
  const wrapper = panel(); await flushPromises()
  await wrapper.find('.progress-toggle').trigger('click')
  const content = wrapper.findAll('.rich-text-content')
  expect(content[0]!.find('strong').text()).toBe('富文本范围')
  expect(content[0]!.find('script').exists()).toBe(false)
  expect(content[1]!.text()).toBe('<b>旧文本范围</b>')
  expect(content[1]!.find('b').exists()).toBe(false)
  wrapper.unmount()
})

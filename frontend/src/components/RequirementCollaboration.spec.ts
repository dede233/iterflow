import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'
const mocks = vi.hoisted(() => ({ read: vi.fn(), replace: vi.fn(), options: vi.fn(), latest: vi.fn(), can: vi.fn() }))
vi.mock('@/api/requirementCollaboration', () => ({ getCollaborators: mocks.read, replaceCollaborators: mocks.replace, listAssigneeOptions: mocks.options }))
vi.mock('@/api/requirements', () => ({ getRequirement: mocks.latest }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: mocks.can }) }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: false }) }))
import Panel from './RequirementCollaboratorsPanel.vue'
import Selector from './RequirementAssigneeSelect.vue'
import ConflictDialog from './RevisionConflictDialog.vue'
const developer = { user_id: 2, display_name: '开发甲', can_develop: true, can_design: false }
const designer = { user_id: 3, display_name: '设计乙', can_develop: false, can_design: true }
const initial = { revision: 8, owner: null, developers: [developer], designers: [designer] }
beforeEach(() => {
  vi.resetAllMocks()
  mocks.read.mockResolvedValue(initial)
  mocks.replace.mockResolvedValue({ ...initial, revision: 9 })
  mocks.options.mockResolvedValue({ items: [developer], total: 1, page: 1, page_size: 50 })
  mocks.can.mockReturnValue(true)
})
async function panel() {
  const wrapper = mount(Panel, { props: { requirementId: 42, revision: 8 }, global: { plugins: [ElementPlus], directives: { loading: {} } }, attachTo: document.body })
  await flushPromises()
  return wrapper
}
it('shows participant names without granting assignment or user management', async () => {
  mocks.can.mockReturnValue(false)
  const wrapper = await panel()
  expect(wrapper.text()).toContain('开发甲')
  expect(wrapper.text()).toContain('设计乙')
  expect(wrapper.text()).toContain('未分配')
  expect(wrapper.text()).not.toContain('分配协作人员')
  expect(mocks.options).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('submits all duties with the freshly loaded revision and refreshes the parent', async () => {
  const wrapper = await panel()
  mocks.read.mockResolvedValue({ ...initial, revision: 10 })
  await wrapper.findAll('button').find(b => b.text() === '分配协作人员')!.trigger('click')
  await flushPromises()
  const selectors = wrapper.findAllComponents(Selector)
  expect(selectors).toHaveLength(3)
  selectors[0]!.vm.$emit('update:modelValue', 7)
  selectors[1]!.vm.$emit('update:modelValue', [2, 4])
  selectors[2]!.vm.$emit('update:modelValue', [3, 4])
  await flushPromises()
  document.querySelectorAll<HTMLButtonElement>('button').forEach(b => { if (b.textContent?.trim() === '保存分工') b.click() })
  await flushPromises()
  expect(mocks.replace).toHaveBeenCalledWith(42, { revision: 10, owner_id: 7, developer_ids: [2, 4], designer_ids: [3, 4] })
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('shows a conflict without retrying or overwriting selected duties', async () => {
  const wrapper = await panel()
  await wrapper.findAll('button').find(b => b.text() === '分配协作人员')!.trigger('click')
  await flushPromises()
  mocks.replace.mockRejectedValue({ response: { status: 409, data: { code: 40910, data: { current_revision: 9, current_updated_at: '2026-10-10T01:00:00Z', current_updated_by: 7 } } } })
  mocks.latest.mockResolvedValue({ title: '最新需求', status: 'CONFIRMED', priority: 'P1', revision: 9 })
  document.querySelectorAll<HTMLButtonElement>('button').forEach(b => { if (b.textContent?.trim() === '保存分工') b.click() })
  await flushPromises()
  expect(wrapper.findComponent(ConflictDialog).props('visible')).toBe(true)
  expect(mocks.replace).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('updated')).toBeUndefined()
  expect(wrapper.findAllComponents(Selector)[1]!.props('modelValue')).toEqual([2])
  wrapper.unmount()
})
it('keeps failed reads visible and allows retry', async () => {
  mocks.read.mockRejectedValueOnce(new Error('network'))
  const wrapper = await panel()
  expect(wrapper.text()).toContain('协作人员加载失败')
  await wrapper.findAll('button').find(b => b.text().includes('重试'))!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('开发甲')
  wrapper.unmount()
})
it('ignores stale autocomplete responses and paginates using the current keyword', async () => {
  const deferred = () => { let resolve!: (value: any) => void; const promise = new Promise<any>(r => { resolve = r }); return { promise, resolve } }
  const first = deferred(), second = deferred()
  mocks.options.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  const wrapper = mount(Selector, { props: { modelValue: [], kind: 'DEVELOPER', selected: [] }, global: { plugins: [ElementPlus] } })
  const remote = wrapper.findComponent({ name: 'ElSelect' }).props('remoteMethod') as (keyword: string) => Promise<void>
  void remote('旧'); void remote('新')
  second.resolve({ items: [developer], total: 51, page: 1, page_size: 50 })
  await flushPromises()
  first.resolve({ items: [designer], total: 1, page: 1, page_size: 50 })
  await flushPromises()
  expect(wrapper.findAllComponents({ name: 'ElOption' }).map(o => o.props('label'))).toEqual(['开发甲'])
  mocks.options.mockResolvedValue({ items: [{ ...developer, user_id: 4, display_name: '开发乙' }], total: 51, page: 2, page_size: 50 })
  await wrapper.findAll('button').find(b => b.text() === '加载更多候选人员')!.trigger('click')
  await flushPromises()
  expect(mocks.options).toHaveBeenLastCalledWith('DEVELOPER', '新', 2)
  expect(wrapper.findAllComponents({ name: 'ElOption' }).map(o => o.props('label'))).toEqual(['开发甲', '开发乙'])
  wrapper.unmount()
})

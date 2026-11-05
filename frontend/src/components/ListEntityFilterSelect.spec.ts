import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import type { FilterOptionKind } from '@/api/filterOptions'
const mocks = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('@/api/filterOptions', () => ({ listFilterOptions: mocks.list }))
import ListEntityFilterSelect from './ListEntityFilterSelect.vue'

beforeEach(() => { vi.resetAllMocks(); setActivePinia(createPinia()); session(['rd.requirement.view', 'rd.version.view']); mocks.list.mockResolvedValue({ items: [], total: 0 }) })
function session(permissions: string[], id = 1) {
  const auth = useAuthStore(); auth.user = { id, permission_codes: permissions } as any; auth.accessToken = `session-${id}`; return auth
}
function panel(kind: FilterOptionKind = 'participant', value: number | null = null) {
  return mount(ListEntityFilterSelect, { props: { kind, label: '参与人', modelValue: value }, global: { stubs: {
    'el-select': { name: 'ElSelect', props: ['modelValue', 'filterMethod', 'disabled'], template: '<section><slot/><slot name="footer"/></section>' },
    'el-option': { name: 'ElOption', props: ['value', 'label'], template: '<span class="option">{{ label }}</span>' },
    'el-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot/></button>' },
  } } })
}
const select = (wrapper: ReturnType<typeof panel>) => wrapper.findComponent({ name: 'ElSelect' })
const open = async (wrapper: ReturnType<typeof panel>) => { select(wrapper).vm.$emit('visible-change', true); await flushPromises() }

it.each(['participant', 'requirement-version', 'owner'] as const)('loads paginated %s candidates only after opening', async kind => {
  mocks.list.mockResolvedValueOnce({ items: [{ id: 1, label: '第一页候选' }], total: 21 }).mockResolvedValueOnce({ items: [{ id: 21, label: '第二页候选' }], total: 21 })
  const wrapper = panel(kind)
  expect(mocks.list).not.toHaveBeenCalled()
  await open(wrapper)
  expect(mocks.list).toHaveBeenLastCalledWith(kind, '', 1)
  await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click'); await flushPromises()
  expect(mocks.list).toHaveBeenLastCalledWith(kind, '', 2)
  expect(wrapper.text()).toContain('第二页候选'); expect(wrapper.text()).not.toContain('第一页候选')
  select(wrapper).vm.$emit('update:modelValue', 21)
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([21])
  wrapper.unmount()
})

it('restores a selected label through the scoped ID lookup rather than enumerating all pages', async () => {
  mocks.list.mockResolvedValue({ items: [{ id: 81, label: '历史参与者（已停用）' }], total: 1 })
  const wrapper = panel('participant', 81); await flushPromises()
  expect(mocks.list).toHaveBeenCalledExactlyOnceWith('participant', '', 1, 81)
  expect(wrapper.text()).toContain('历史参与者（已停用）')
  select(wrapper).vm.$emit('update:modelValue', undefined)
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([null])
  await wrapper.setProps({ modelValue: null }); await flushPromises()
  expect(wrapper.text()).not.toContain('历史参与者'); wrapper.unmount()
})

it('uses parent requirement view permission for scoped version filter labels', async () => {
  session(['rd.requirement.view'])
  mocks.list.mockResolvedValue({ items: [{ id: 7, label: '版本 #7（无查看权限）' }], total: 1 })
  const wrapper = panel('requirement-version', 7); await flushPromises(); await open(wrapper)
  expect(wrapper.text()).toContain('版本 #7（无查看权限）')
  expect(mocks.list).toHaveBeenCalledTimes(2); wrapper.unmount()
})

it('does not request candidates or names without the parent domain permission, but permits clearing an existing ID', async () => {
  session(['rd.feedback.view'])
  const wrapper = panel('owner', 9); await flushPromises(); await open(wrapper)
  expect(mocks.list).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('#9')
  select(wrapper).vm.$emit('update:modelValue', '')
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([null]); wrapper.unmount()
})

it('debounces remote keywords and discards late results for a previous query', async () => {
  let finishOld!: (value: unknown) => void
  mocks.list.mockResolvedValueOnce({ items: [], total: 0 }).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve })).mockResolvedValueOnce({ items: [{ id: 3, label: '最新搜索' }], total: 1 })
  const wrapper = panel(); await open(wrapper)
  vi.useFakeTimers()
  select(wrapper).props('filterMethod')('旧词')
  await vi.advanceTimersByTimeAsync(251)
  select(wrapper).props('filterMethod')('新词')
  await vi.advanceTimersByTimeAsync(251)
  vi.useRealTimers(); await flushPromises()
  finishOld({ items: [{ id: 2, label: '过期搜索' }], total: 1 }); await flushPromises()
  expect(mocks.list.mock.calls.map(call => call.slice(1))).toEqual([['', 1], ['旧词', 1], ['新词', 1]])
  expect(wrapper.text()).toContain('最新搜索'); expect(wrapper.text()).not.toContain('过期搜索'); wrapper.unmount()
})

it('retries the failed page without skipping to another page', async () => {
  mocks.list.mockResolvedValueOnce({ items: [{ id: 1, label: '首个' }], total: 21 }).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ items: [{ id: 21, label: '第二页' }], total: 21 })
  const wrapper = panel(); await open(wrapper)
  await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('加载失败')
  await wrapper.findAll('button').find(button => button.text() === '重试')!.trigger('click'); await flushPromises()
  expect(mocks.list.mock.calls.map(call => call[2])).toEqual([1, 2, 2])
  expect(wrapper.text()).toContain('第二页'); wrapper.unmount()
})

it('removes previous account labels and ignores in-flight lookups and search responses', async () => {
  const auth = useAuthStore()
  let finishLookup!: (value: unknown) => void, finishSearch!: (value: unknown) => void
  mocks.list.mockImplementationOnce(() => new Promise(resolve => { finishLookup = resolve })).mockImplementationOnce(() => new Promise(resolve => { finishSearch = resolve }))
  const wrapper = panel('participant', 41); await open(wrapper)
  auth.user = { id: 2, permission_codes: ['rd.feedback.view'] } as any
  await flushPromises()
  finishLookup({ items: [{ id: 41, label: '旧账号私有姓名' }], total: 1 })
  finishSearch({ items: [{ id: 42, label: '旧账号候选' }], total: 1 })
  await flushPromises()
  expect(wrapper.text()).not.toContain('旧账号'); expect(mocks.list).toHaveBeenCalledTimes(2)
  wrapper.unmount()
})

it('keeps only a neutral ID fallback for unavailable selected values', async () => {
  mocks.list.mockResolvedValue({ items: [], total: 0 })
  const wrapper = panel('owner', 99); await flushPromises()
  expect(wrapper.text()).toBe('已选择 参与人 #99')
  wrapper.unmount()
})

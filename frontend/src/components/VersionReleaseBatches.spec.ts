import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'
const mocks = vi.hoisted(() => ({ list: vi.fn(), options: vi.fn(), create: vi.fn(), complete: vi.fn(), adjust: vi.fn(), cancel: vi.fn(), finalize: vi.fn(), allowed: true }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => mocks.allowed }) }))
vi.mock('@/api/targetReleases', async original => ({ ...await original<typeof import('@/api/targetReleases')>(), listBatches: mocks.list, versionTargets: mocks.options, createBatch: mocks.create, completeTarget: mocks.complete, adjustBatch: mocks.adjust, cancelBatch: mocks.cancel, finalizeBatch: mocks.finalize }))
import VersionReleaseBatches from './VersionReleaseBatches.vue'
const ver = { id: 7, revision: 4, status: 'READY', system_id: 1, release_frozen: false } as any
const row = { id: 101, target_id: 1, name: '小程序 A', code: 'A', platform: 'WECHAT_MINI_PROGRAM', active: true, completed_at: null, revision: 2 }
const batch = { id: 9, version_id: 7, system_id: 1, kind: 'INITIAL', status: 'IN_PROGRESS', revision: 3, total: 2, completed: 1, release_notes: '本批说明', targets: [row, { ...row, id: 102, target_id: 2, name: '小程序 B', completed_at: '2026-11-09T10:00:00Z' }] }
const state = (items: any[] = []) => ({ version_id: 7, version_revision: 4, system_id: 1, release_frozen: items.length > 0, legacy_unrecorded: false, coverage_count: 1, items, page: 1, page_size: 20, total: items.length })
const mountView = (version = ver) => mount(VersionReleaseBatches, { props: { version }, global: { plugins: [ElementPlus], stubs: { teleport: true } } })
const click = async (wrapper: ReturnType<typeof mountView>, label: string) => { await wrapper.findAll('button').find(b => b.text() === label)!.trigger('click'); await flushPromises() }
beforeEach(() => {
  vi.clearAllMocks(); mocks.allowed = true
  mocks.list.mockResolvedValue(state())
  mocks.options.mockResolvedValue([{ id: 1, name: '小程序 A', code: 'A', platform: 'WECHAT_MINI_PROGRAM', covered: false, pending: false }])
  mocks.complete.mockResolvedValue(batch); mocks.create.mockResolvedValue(batch)
})
it('shows target progress and freezes the initial creation entry', async () => {
  mocks.list.mockResolvedValue(state([batch]))
  const wrapper = mountView(); await flushPromises()
  expect(wrapper.text()).toContain('进行中 · 1/2')
  expect(wrapper.text()).toContain('需求清单、内容及人员已冻结')
  expect(wrapper.text()).not.toContain('创建首次发布计划')
  await click(wrapper, '登记 小程序 A 实际上线')
  await click(wrapper, '确认实际已上线')
  expect(mocks.complete).toHaveBeenCalledWith(7, 9, 101, expect.objectContaining({ version_revision: 4, batch_revision: 3, revision: 2 }))
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('offers a read-only history without write buttons', async () => {
  mocks.allowed = false; mocks.list.mockResolvedValue(state([batch]))
  const wrapper = mountView(); await flushPromises()
  expect(wrapper.text()).toContain('小程序 A')
  expect(wrapper.findAll('button').filter(b => /登记|调整|创建|取消未完成/.test(b.text()))).toHaveLength(0)
  wrapper.unmount()
})
it('keeps the dialog open with actionable publish blockers', async () => {
  mocks.create.mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { code: 40923, message: '发布检查未通过', data: { checks: [{ type: 'R', passed: false, message: '需求待重新确认' }] } } } })
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '创建首次发布计划')
  const select = wrapper.findComponent({ name: 'ElCheckboxGroup' }); select.vm.$emit('update:modelValue', [1])
  await wrapper.find('textarea').setValue('本批发布说明')
  await click(wrapper, '确认计划')
  expect(mocks.create).toHaveBeenCalledWith(7, expect.objectContaining({ target_ids: [1], version_revision: 4, kind: 'INITIAL' }))
  expect(wrapper.text()).toContain('需求待重新确认')
  wrapper.unmount()
})
it('reloads after stale revision without replaying a successful-looking write', async () => {
  mocks.list.mockResolvedValue(state([batch]))
  mocks.complete.mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { code: 40910, message: '已变更' } } })
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '登记 小程序 A 实际上线'); await click(wrapper, '确认实际已上线')
  expect(mocks.complete).toHaveBeenCalledTimes(1)
  expect(mocks.list).toHaveBeenCalledTimes(2)
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('explains missing legacy coverage and offers later supplement batches', async () => {
  mocks.list.mockResolvedValue({ ...state(), legacy_unrecorded: true })
  const wrapper = mountView({ ...ver, status: 'RELEASED' }); await flushPromises()
  expect(wrapper.text()).toContain('历史发布，未记录目标')
  await click(wrapper, '新增补发 / 重新发布')
  expect(wrapper.text()).toContain('已覆盖目标重新发布')
  wrapper.unmount()
})
it('retries a failed panel load', async () => {
  mocks.list.mockRejectedValueOnce(new Error('offline'))
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '重新加载')
  expect(mocks.list).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('暂无目标发布计划')
  wrapper.unmount()
})

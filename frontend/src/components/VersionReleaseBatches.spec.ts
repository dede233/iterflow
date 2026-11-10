import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'
const mocks = vi.hoisted(() => ({ list: vi.fn(), options: vi.fn(), record: vi.fn(), allowed: true }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => mocks.allowed }) }))
vi.mock('@/api/targetReleases', async original => ({ ...await original<typeof import('@/api/targetReleases')>(), listBatches: mocks.list, versionTargets: mocks.options, recordCoverage: mocks.record }))
import VersionReleaseBatches from './VersionReleaseBatches.vue'
const ver = { id: 7, revision: 4, status: 'RELEASED', system_id: 1, release_frozen: false } as any
const row = { id: 101, target_id: 1, name: '小程序 A', code: 'A', platform: 'WECHAT_MINI_PROGRAM', active: true, completed_at: null, revision: 2 }
const batch = { id: 9, version_id: 7, system_id: 1, kind: 'INITIAL', status: 'CANCELED', revision: 3, total: 2, completed: 1, release_notes: '本批说明', targets: [row, { ...row, id: 102, target_id: 2, name: 'PC B', completed_at: '2026-11-09T10:00:00Z' }] }
const state = (items: any[] = []) => ({ version_id: 7, version_revision: 4, system_id: 1, release_frozen: false, legacy_unrecorded: false, coverage_count: items.length ? 1 : 0, items, page: 1, page_size: 20, total: items.length })
const mountView = (version = ver) => mount(VersionReleaseBatches, { props: { version }, global: { plugins: [ElementPlus], stubs: { teleport: true } } })
const click = async (wrapper: ReturnType<typeof mountView>, label: string) => { await wrapper.findAll('button').find(b => b.text() === label)!.trigger('click'); await flushPromises() }
beforeEach(() => {
  vi.clearAllMocks(); mocks.allowed = true
  mocks.list.mockResolvedValue(state())
  mocks.options.mockResolvedValue([
    { id: 1, name: '小程序 A', code: 'A', platform: 'WECHAT_MINI_PROGRAM', covered: false, pending: true },
    { id: 2, name: 'PC B', code: 'B', platform: 'PC_WEB', covered: true, pending: false },
  ])
  mocks.record.mockResolvedValue(batch)
})
it('preserves old partial success without implying the uncompleted target was published', async () => {
  mocks.list.mockResolvedValue(state([batch]))
  const wrapper = mountView(); await flushPromises()
  expect(wrapper.text()).toContain('旧计划未登记发布，不计入已发布范围')
  expect(wrapper.text()).not.toContain('创建首次发布计划')
  expect(wrapper.findAll('button').some(b => /调整|确认整体上线|登记 .* 实际上线/.test(b.text()))).toBe(false)
  wrapper.unmount()
})
it('records multiple coverage selections in one write and keeps completed targets checked and locked', async () => {
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '补记已发布目标')
  const checkboxes = wrapper.findAll('input[type="checkbox"]')
  expect(checkboxes[1].attributes('disabled')).toBeDefined()
  expect((checkboxes[1].element as HTMLInputElement).checked).toBe(true)
  await checkboxes[0].setValue(true)
  await click(wrapper, '保存已发布目标')
  expect(mocks.record).toHaveBeenCalledWith(7, expect.objectContaining({ version_revision: 4, target_ids: [1], system_id: 1 }))
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('hides the supplement entry until normal publication and for read-only viewers', async () => {
  const wrapper = mountView({ ...ver, status: 'READY' }); await flushPromises()
  expect(wrapper.text()).toContain('无需先创建目标计划')
  expect(wrapper.findAll('button').some(b => b.text() === '补记已发布目标')).toBe(false)
  mocks.allowed = false; await wrapper.setProps({ version: { ...ver, revision: 5 } }); await flushPromises()
  expect(wrapper.findAll('button').some(b => b.text() === '补记已发布目标')).toBe(false)
  wrapper.unmount()
})
it('does not write an empty selection and retains server errors', async () => {
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '补记已发布目标'); await click(wrapper, '保存已发布目标')
  expect(mocks.record).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('请勾选至少一个已经发布的目标')
  mocks.record.mockRejectedValue({ isAxiosError: true, response: { data: { code: 40983, message: '目标已经登记，请刷新' } } })
  await wrapper.find('input[type="checkbox"]').setValue(true); await click(wrapper, '保存已发布目标')
  expect(wrapper.text()).toContain('目标已经登记，请刷新')
  wrapper.unmount()
})
it('reloads stale revision without silently retrying the write', async () => {
  mocks.record.mockRejectedValue({ isAxiosError: true, response: { data: { code: 40910, message: '已变更' } } })
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '补记已发布目标')
  await wrapper.find('input[type="checkbox"]').setValue(true); await click(wrapper, '保存已发布目标')
  expect(mocks.record).toHaveBeenCalledTimes(1); expect(mocks.list).toHaveBeenCalledTimes(2)
  expect(wrapper.emitted('updated')).toHaveLength(1)
  wrapper.unmount()
})
it('retries a failed load', async () => {
  mocks.list.mockRejectedValueOnce(new Error('offline'))
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '重新加载')
  expect(mocks.list).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('尚未记录发布目标')
  wrapper.unmount()
})
it('never reuses stale options when opening a different version', async () => {
  let resolve!: (value: any) => void
  mocks.options.mockImplementationOnce(() => new Promise(r => { resolve = r }))
  const wrapper = mountView(); await flushPromises(); await click(wrapper, '补记已发布目标')
  await wrapper.setProps({ version: { ...ver, id: 8 } }); await flushPromises()
  resolve([{ id: 99, name: '别的版本目标', code: 'X', platform: 'PC_WEB' }]); await flushPromises()
  await click(wrapper, '补记已发布目标')
  expect(wrapper.text()).not.toContain('别的版本目标')
  wrapper.unmount()
})

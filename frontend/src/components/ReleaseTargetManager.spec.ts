import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ElementPlus, { ElMessageBox } from 'element-plus'
const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), update: vi.fn() }))
vi.mock('@/api/targetReleases', async original => ({ ...await original<typeof import('@/api/targetReleases')>(), listTargets: mocks.list,
  createMiniProgramTarget: mocks.create, updateMiniProgramTarget: mocks.update }))
import ReleaseTargetManager from './ReleaseTargetManager.vue'

const rows = [
  { id: 1, system_id: 1, code: 'A_WX', name: '开电', platform: 'WECHAT_MINI_PROGRAM', app_id: 'wx1234', enabled: true, revision: 2 },
  { id: 2, system_id: 1, code: 'A_ALIPAY', name: '开电', platform: 'ALIPAY_MINI_PROGRAM', app_id: '20210001', enabled: false, revision: 3 },
  { id: 3, system_id: 1, code: 'B_WX', name: '开芯', platform: 'WECHAT_MINI_PROGRAM', app_id: 'wx5678', enabled: true, revision: 4 },
  { id: 4, system_id: 1, code: 'PC', name: '官网', platform: 'PC_WEB', url: 'https://example.com', enabled: true, revision: 1 },
]
const createView = () => mount(ReleaseTargetManager, { attachTo: document.body, props: { systemId: 1, systemName: '测试系统' }, global: { plugins: [ElementPlus], stubs: { teleport: true } } })
const click = async (wrapper: ReturnType<typeof createView>, label: string) => { await wrapper.findAll('button').find(b => b.text() === label)!.trigger('click'); await flushPromises() }
beforeEach(() => { vi.clearAllMocks(); mocks.list.mockResolvedValue(rows); mocks.create.mockResolvedValue([]); mocks.update.mockResolvedValue([]) })
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = '' })

it('searches brand names, codes and AppIDs without duplicating brand rows', async () => {
  const wrapper = createView(); await flushPromises()
  expect(wrapper.findAll('article')).toHaveLength(3)
  await wrapper.find('input[aria-label="搜索发布目标"]').setValue('20210001')
  expect(wrapper.findAll('article')).toHaveLength(1)
  expect(wrapper.find('article').text()).toContain('开电')
  await wrapper.find('input[aria-label="搜索发布目标"]').setValue('不存在')
  expect(wrapper.text()).toContain('没有符合条件的目标')
  wrapper.unmount()
})
it('distinguishes missing configuration from disabled platforms and PC sites', async () => {
  const wrapper = createView(); await flushPromises()
  expect(wrapper.findAll('article')[0].text()).toContain('已停用')
  expect(wrapper.findAll('article')[1].text()).toContain('未配置')
  expect(wrapper.findAll('article')[2].text()).not.toContain('未配置')
  await wrapper.find('select[aria-label="发布目标配置筛选"]').setValue('MISSING'); await flushPromises()
  expect(wrapper.findAll('article')).toHaveLength(1)
  expect(wrapper.find('article').text()).toContain('开芯')
  wrapper.unmount()
})
it('places validation beside empty required fields without issuing a write', async () => {
  const wrapper = createView(); await flushPromises(); await click(wrapper, '新增发布目标'); await click(wrapper, '保存目标')
  const messages = wrapper.findAll('.field-error').map(e => e.text())
  expect(messages).toEqual(expect.arrayContaining(['请填写目标名称', '请填写目标编码', '请填写微信小程序 AppID']))
  expect(mocks.create).not.toHaveBeenCalled()
  await wrapper.findAll('.el-dialog input')[0].setValue('已补充目标名称')
  expect(wrapper.findAll('.field-error').map(e => e.text())).not.toContain('请填写目标名称')
  expect(wrapper.text()).toContain('请填写目标编码')
  wrapper.unmount()
})
it('keeps edits when discard is declined and closes only after confirmation', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel').mockResolvedValueOnce('confirm')
  const wrapper = createView(); await flushPromises(); await click(wrapper, '新增发布目标')
  await wrapper.findAll('.el-dialog input')[0].setValue('尚未保存')
  await click(wrapper, '取消')
  expect(confirm).toHaveBeenCalledTimes(1)
  expect((wrapper.findAll('.el-dialog input')[0].element as HTMLInputElement).value).toBe('尚未保存')
  await click(wrapper, '取消')
  expect(confirm).toHaveBeenCalledTimes(2)
  expect(mocks.create).not.toHaveBeenCalled()
  wrapper.unmount()
})
it('preserves both member revisions and independent platform state when editing a brand', async () => {
  const wrapper = createView(); await flushPromises()
  await wrapper.find('button[aria-label="编辑发布目标 开电"]').trigger('click'); await flushPromises()
  await wrapper.findAll('.el-dialog input')[0].setValue('开电改名')
  await click(wrapper, '保存目标')
  expect(mocks.update).toHaveBeenCalledWith(1, expect.objectContaining({ name: '开电改名', members: [{ id: 1, revision: 2 }, { id: 2, revision: 3 }],
    platforms: [{ platform: 'WECHAT_MINI_PROGRAM', app_id: 'wx1234', enabled: true }, { platform: 'ALIPAY_MINI_PROGRAM', app_id: '20210001', enabled: false }] }))
  wrapper.unmount()
})

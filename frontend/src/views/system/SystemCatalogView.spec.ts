import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ElementPlus, { ElDialog, ElMessageBox } from 'element-plus'
import SystemCatalogView from './SystemCatalogView.vue'
const mocks = vi.hoisted(() => ({ list: vi.fn(), update: vi.fn(), guards: [] as Array<() => Promise<boolean>> }))
vi.mock('@/api/systems', () => ({ listManagedSystems: () => Promise.resolve({ systems: [{ id: 1, code: 'A', name: '系统A', enabled: true, revision: 1 }] }) }))
vi.mock('@/api/targetReleases', async original => ({ ...await original<typeof import('@/api/targetReleases')>(), listTargets: mocks.list, updateMiniProgramTarget: mocks.update }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: true }) }))
vi.mock('vue-router', () => ({ onBeforeRouteLeave: (guard: () => Promise<boolean>) => mocks.guards.push(guard) }))
const wrappers: ReturnType<typeof mount>[] = []
const click = async (wrapper: ReturnType<typeof mount>, label: string) => { await wrapper.findAll('button').find(button => button.text() === label)!.trigger('click'); await flushPromises() }
async function view() {
  const wrapper = mount(SystemCatalogView, { attachTo: document.body, global: { plugins: [ElementPlus], stubs: { teleport: true } } })
  wrappers.push(wrapper); await flushPromises(); await click(wrapper, '发布目标')
  await wrapper.get('button[aria-label="编辑发布目标 开电"]').trigger('click'); await flushPromises()
  await wrapper.get('input[placeholder="如：开电"]').setValue('开电更新')
  return wrapper
}
function outerClose(wrapper: ReturnType<typeof mount>) { return wrapper.findAllComponents(ElDialog).find(dialog => dialog.props('title') === '管理发布目标')!.props('beforeClose')! }
beforeEach(() => {
  vi.clearAllMocks(); mocks.guards.length = 0
  mocks.list.mockResolvedValue([{ id: 1, system_id: 1, code: 'A_WX', name: '开电', platform: 'WECHAT_MINI_PROGRAM', app_id: 'wx123', enabled: true, revision: 2 }])
})
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.restoreAllMocks(); document.body.innerHTML = '' })
it('protects a brand draft from the outer directory close and route navigation', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  const wrapper = await view(); const done = vi.fn()
  await outerClose(wrapper)(done)
  expect(done).not.toHaveBeenCalled()
  expect(await mocks.guards[0]!()).toBe(false)
  expect((wrapper.get('input[placeholder="如：开电"]').element as HTMLInputElement).value).toBe('开电更新')
  confirm.mockResolvedValue('confirm')
  await outerClose(wrapper)(done)
  expect(done).toHaveBeenCalledTimes(1)
})
it('blocks outer close and navigation during save and allows both after success', async () => {
  let resolve!: () => void
  mocks.update.mockImplementation(() => new Promise<void>(done => { resolve = done }))
  const confirm = vi.spyOn(ElMessageBox, 'confirm')
  const wrapper = await view(); await click(wrapper, '保存目标')
  const done = vi.fn(); await outerClose(wrapper)(done)
  expect(done).not.toHaveBeenCalled()
  expect(await mocks.guards[0]!()).toBe(false)
  resolve(); await flushPromises()
  await outerClose(wrapper)(done)
  expect(done).toHaveBeenCalledTimes(1)
  expect(await mocks.guards[0]!()).toBe(true)
  expect(confirm).not.toHaveBeenCalled()
})

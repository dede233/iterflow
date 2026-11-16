import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({ versionClose: vi.fn(), releaseClose: vi.fn(), push: vi.fn() }))
vi.mock('@/composables/useResponsive', () => ({ useResponsive: () => ({ isMobile: false }) }))
vi.mock('@/composables/usePermission', () => ({ usePermission: () => ({ can: () => true }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/views/version/VersionDetailView.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { __esModule: true, default: defineComponent({
    name: 'VersionDetailView', props: ['embeddedId'], emits: ['close', 'open-release'],
    setup(props, { emit, expose }) {
      expose({ requestClose: mocks.versionClose })
      return () => h('div', [h('p', `版本 ${props.embeddedId}`),
        h('button', { onClick: () => emit('close') }, '内层关闭'),
        h('button', { onClick: () => emit('open-release', 8) }, '查看发布记录')])
    },
  }) }
})
vi.mock('@/views/release/ReleaseDetailView.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return { __esModule: true, default: defineComponent({
    name: 'ReleaseDetailView', props: ['embeddedId'],
    setup(props, { expose }) {
      expose({ requestClose: mocks.releaseClose })
      return () => h('p', `发布记录 ${props.embeddedId}`)
    },
  }) }
})
import ReleaseVersionDrawer from './ReleaseVersionDrawer.vue'

const createView = () => mount(ReleaseVersionDrawer, {
  props: { modelValue: true, kind: 'version', id: 7, returnTo: '/versions' },
  global: { plugins: [ElementPlus], stubs: { teleport: true } },
})
const click = async (wrapper: ReturnType<typeof createView>, label: string) => {
  await wrapper.findAll('button').find(button => button.text() === label)!.trigger('click')
  await flushPromises()
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.versionClose.mockResolvedValue(true)
  mocks.releaseClose.mockResolvedValue(true)
  mocks.push.mockResolvedValue(undefined)
})

it('asks the detail before closing from the drawer or an inner close action', async () => {
  const wrapper = createView(); await flushPromises()
  const done = vi.fn()
  const close = wrapper.getComponent({ name: 'ElDrawer' }).props('beforeClose')
  mocks.versionClose.mockResolvedValue(false)
  await close(done)
  await click(wrapper, '内层关闭')
  expect(done).not.toHaveBeenCalled()
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  mocks.versionClose.mockResolvedValue(true)
  await close(done)
  expect(done).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})

it('does not open the full page while a detail refuses to leave', async () => {
  const wrapper = createView(); await flushPromises()
  mocks.versionClose.mockResolvedValue(false)
  await click(wrapper, '打开完整页面')
  expect(mocks.push).not.toHaveBeenCalled()
  mocks.versionClose.mockResolvedValue(true)
  await click(wrapper, '打开完整页面')
  expect(mocks.push).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  wrapper.unmount()
})

it('guards both related-detail navigation and history return', async () => {
  const wrapper = createView(); await flushPromises()
  mocks.versionClose.mockResolvedValue(false)
  await click(wrapper, '查看发布记录')
  expect(wrapper.text()).toContain('版本 7')
  mocks.versionClose.mockResolvedValue(true)
  await click(wrapper, '查看发布记录')
  expect(wrapper.text()).toContain('发布记录 8')
  mocks.releaseClose.mockResolvedValue(false)
  await click(wrapper, '返回上个详情')
  expect(wrapper.text()).toContain('发布记录 8')
  mocks.releaseClose.mockResolvedValue(true)
  await click(wrapper, '返回上个详情')
  expect(wrapper.text()).toContain('版本 7')
  wrapper.unmount()
})

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import type { EntityDeleteKind } from '@/api/entityActions'
import EntityLifecycleMenu from './EntityLifecycleMenu.vue'

const mocks = vi.hoisted(() => ({ remove: vi.fn(), withdraw: vi.fn(), success: vi.fn() }))
vi.mock('@/api/entityActions', () => ({ deleteEntity: mocks.remove }))
vi.mock('@/api/adProductions', () => ({ withdrawAdProduction: mocks.withdraw }))
vi.mock('element-plus', () => ({ ElMessage: { success: mocks.success } }))

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: [] } as any
})

function panel(kind: EntityDeleteKind = 'requirements', action: 'delete' | 'withdraw' = 'delete') {
  return mount(EntityLifecycleMenu, {
    props: { kind, action, id: 4, revision: 3, title: '待处理记录' },
    global: { stubs: {
      'el-dropdown': { name: 'ElDropdown', template: '<div><slot /><slot name="dropdown" /></div>' },
      'el-dropdown-menu': { template: '<div><slot /></div>' },
      'el-dropdown-item': { template: '<div><slot /></div>' },
      'el-dialog': { props: ['modelValue'], template: '<section v-if="modelValue"><slot /></section>' },
      'el-button': { template: '<button><slot /></button>' },
      'el-form': { template: '<form><slot /></form>' },
      'el-form-item': { template: '<div><slot /></div>' },
      'el-input': {
        props: ['modelValue'],
        template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
      },
    } },
  })
}

async function openAction(wrapper: ReturnType<typeof panel>): Promise<void> {
  wrapper.getComponent({ name: 'ElDropdown' }).vm.$emit('command')
  await wrapper.vm.$nextTick()
}

it('requires an explicit reason and retains input on revision conflict without replay', async () => {
  mocks.remove.mockRejectedValue({ response: { status: 409, data: { message: '内容已变化' } } })
  const wrapper = panel()
  await openAction(wrapper)
  await wrapper.get('form').trigger('submit')
  expect(mocks.remove).not.toHaveBeenCalled()

  await wrapper.get('textarea').setValue('重复记录')
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(mocks.remove).toHaveBeenCalledExactlyOnceWith('requirements', 4, { revision: 3, reason: '重复记录' })
  expect(wrapper.get('[role="alert"]').text()).toContain('内容已变化')
  expect(wrapper.get('textarea').element.value).toBe('重复记录')
  expect(wrapper.emitted('deleted')).toBeUndefined()
  wrapper.unmount()
})

it('emits completion and closes the confirmation after deleting a version', async () => {
  mocks.remove.mockResolvedValue({ id: 4, revision: 4, deleted: true })
  const wrapper = panel('versions')
  expect(wrapper.get('button').text()).toBe('更多')
  await openAction(wrapper)
  await wrapper.get('textarea').setValue('  重复规划  ')
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(mocks.remove).toHaveBeenCalledExactlyOnceWith('versions', 4, { revision: 3, reason: '重复规划' })
  expect(wrapper.emitted('deleted')).toEqual([[]])
  expect(wrapper.find('section').exists()).toBe(false)
  wrapper.unmount()
})

it('withdraws over the dedicated action and emits the returned record', async () => {
  const updated = { id: 4, revision: 4, status: 'WITHDRAWN' }
  mocks.withdraw.mockResolvedValue(updated)
  const wrapper = panel('ad-productions', 'withdraw')
  await openAction(wrapper)
  await wrapper.get('textarea').setValue('物料需求有变')
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(mocks.withdraw).toHaveBeenCalledExactlyOnceWith(4, { revision: 3, reason: '物料需求有变' })
  expect(mocks.remove).not.toHaveBeenCalled()
  expect(wrapper.emitted('withdrawn')).toEqual([[updated]])
  expect(wrapper.find('section').exists()).toBe(false)
  wrapper.unmount()
})

it('does not apply delete completion after account switching', async () => {
  let resolve!: (value: unknown) => void
  mocks.remove.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel()
  await openAction(wrapper)
  await wrapper.get('textarea').setValue('重复记录')
  await wrapper.get('form').trigger('submit')
  useAuthStore().user = { id: 2, permission_codes: [] } as any
  await flushPromises()

  resolve({ id: 4, revision: 4, deleted: true })
  await flushPromises()
  expect(wrapper.emitted('deleted')).toBeUndefined()
  expect(wrapper.find('section').exists()).toBe(false)
  wrapper.unmount()
})

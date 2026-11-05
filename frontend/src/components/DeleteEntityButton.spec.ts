import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
const mocks = vi.hoisted(() => ({ remove: vi.fn() }))
vi.mock('@/api/entityActions', () => ({ deleteEntity: mocks.remove }))
import DeleteEntityButton from './DeleteEntityButton.vue'
beforeEach(() => { vi.resetAllMocks(); setActivePinia(createPinia()); useAuthStore().user = { id: 1, permission_codes: [] } as any })
function panel() { return mount(DeleteEntityButton, { props: { kind: 'requirements', id: 4, revision: 3, title: '待确认需求' }, global: { stubs: {
  'el-dialog': { props: ['modelValue'], template: '<section v-if="modelValue"><slot/></section>' },
  'el-button': { template: '<button><slot/></button>' }, 'el-form': { template: '<form><slot/></form>' }, 'el-form-item': { template: '<div><slot/></div>' },
  'el-input': { props: ['modelValue'], template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
} } }) }
it('requires an explicit reason and retains input on revision conflict without replay', async () => {
  mocks.remove.mockRejectedValue({ response: { status: 409, data: { message: '内容已变化' } } })
  const wrapper = panel(); await wrapper.get('button').trigger('click')
  await wrapper.get('form').trigger('submit'); expect(mocks.remove).not.toHaveBeenCalled()
  await wrapper.get('textarea').setValue('重复记录'); await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.remove).toHaveBeenCalledExactlyOnceWith('requirements', 4, { revision: 3, reason: '重复记录' })
  expect(wrapper.get('textarea').element.value).toBe('重复记录'); expect(wrapper.emitted('deleted')).toBeUndefined()
  wrapper.unmount()
})
it('does not apply delete completion after account switching', async () => {
  let resolve!: (value: unknown) => void
  mocks.remove.mockReturnValue(new Promise(r => { resolve = r }))
  const wrapper = panel(); await wrapper.get('button').trigger('click'); await wrapper.get('textarea').setValue('重复记录'); await wrapper.get('form').trigger('submit')
  useAuthStore().user = { id: 2, permission_codes: [] } as any; await flushPromises()
  resolve({ id: 4, revision: 4, deleted: true }); await flushPromises()
  expect(wrapper.emitted('deleted')).toBeUndefined(); expect(wrapper.find('section').exists()).toBe(false); wrapper.unmount()
})

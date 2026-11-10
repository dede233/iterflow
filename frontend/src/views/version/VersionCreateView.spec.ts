import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'

const mocks = vi.hoisted(() => ({ create: vi.fn(), replace: vi.fn(), back: vi.fn(), success: vi.fn(), warning: vi.fn() }))
vi.mock('@/api/versions', () => ({ createVersion: mocks.create }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: mocks.replace, back: mocks.back }) }))
vi.mock('element-plus', () => ({ ElMessage: { success: mocks.success, warning: mocks.warning } }))
import VersionCreateView from './VersionCreateView.vue'

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  useAuthStore().user = { id: 1, permission_codes: ['*'] } as any
  mocks.create.mockResolvedValue({ id: 9 })
})
function panel(requirement?: { id: number; revision: number; title: string; system_id?: number | null }) {
  return mount(VersionCreateView, { props: { embedded: true, requirement: requirement ? { system_id: 1, ...requirement } : undefined }, global: { stubs: {
    BusinessSystemSelect: { props: ['modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><option value="">选择</option><option value="1">系统甲</option></select>' },
    SectionCard: { template: '<section><slot/></section>' },
    'el-form': { template: '<form><slot/></form>' },
    'el-form-item': { props: ['label', 'error'], template: '<label>{{ label }}<slot/><span v-if="error" role="alert">{{ error }}</span></label>' },
    'el-input': { props: ['modelValue', 'type'], template: '<textarea v-if="type === \'textarea\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"/><input v-else :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"/>' },
    'el-date-picker': { template: '<div />' },
    'el-button': { props: ['disabled', 'loading', 'nativeType'], template: '<button :disabled="disabled || loading" :type="nativeType || \'button\'"><slot/></button>' },
  } } })
}

it('keeps regular version creation independent of requirements', async () => {
  const wrapper = panel()
  await wrapper.get('select').setValue('1')
  await wrapper.get('select').setValue('1')
  const inputs = wrapper.findAll('input')
  expect(inputs[1].element.value).toBe('')
  await inputs[0].setValue(' V1 ')
  await inputs[1].setValue(' 常规版本 ')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).toHaveBeenCalledExactlyOnceWith({ system_id: 1, version_no: 'V1', name: '常规版本', planned_release_date: null, description: null })
  expect(wrapper.emitted('created')).toEqual([[9]])
  wrapper.unmount()
})

it('defaults the version name from its source requirement and submits one atomic request', async () => {
  const wrapper = panel({ id: 7, revision: 4, title: '来源需求' })
  expect(wrapper.findAll('input')[1].element.value).toBe('来源需求')
  await wrapper.findAll('input')[0].setValue('V2')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).toHaveBeenCalledExactlyOnceWith({ system_id: 1, version_no: 'V2', name: '来源需求', planned_release_date: null, description: null, requirement_id: 7, requirement_revision: 4 })
  expect(wrapper.emitted('created')).toEqual([[9]])
  wrapper.unmount()
})

it('shows duplicate number errors inline, preserves all input and allows correction', async () => {
  mocks.create.mockRejectedValueOnce({ response: { status: 409, data: { code: 40934, message: '版本号「V1」已存在，请更换版本号', data: { field: 'version_no', reason: 'duplicate' } } } })
  const wrapper = panel()
  await wrapper.get('select').setValue('1')
  await wrapper.findAll('input')[0].setValue('V1')
  await wrapper.findAll('input')[1].setValue('保留名称')
  await wrapper.get('textarea').setValue('保留说明')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('版本号「V1」已存在')
  expect(wrapper.findAll('input')[1].element.value).toBe('保留名称')
  expect(wrapper.get('textarea').element.value).toBe('保留说明')
  expect(wrapper.emitted('created')).toBeUndefined()
  await wrapper.findAll('input')[0].setValue('V2')
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).toHaveBeenCalledTimes(2)
  expect(wrapper.emitted('created')).toEqual([[9]])
  wrapper.unmount()
})

it('locks duplicate submissions synchronously while the request is pending', async () => {
  let finish!: (value: unknown) => void
  mocks.create.mockReturnValue(new Promise(resolve => { finish = resolve }))
  const wrapper = panel({ id: 7, revision: 4, title: '来源需求' })
  await wrapper.findAll('input')[0].setValue('V1')
  void wrapper.get('form').trigger('submit')
  await wrapper.get('form').trigger('submit')
  expect(mocks.create).toHaveBeenCalledTimes(1)
  expect(wrapper.emitted('saving')).toEqual([[true]])
  finish({ id: 9 }); await flushPromises()
  expect(wrapper.emitted('saving')).toEqual([[true], [false]])
  wrapper.unmount()
})

it('preserves form input on requirement conflict and requires explicit submission after refresh', async () => {
  mocks.create.mockRejectedValueOnce({ response: { status: 409, data: { code: 40910, message: '需求已变化', data: { current_revision: 5 } } } })
  const wrapper = panel({ id: 7, revision: 4, title: '来源需求' })
  await wrapper.findAll('input')[0].setValue('V1')
  await wrapper.findAll('input')[1].setValue('人工修改名称')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('请先刷新需求')
  await wrapper.findAll('button').find(button => button.text() === '刷新需求')!.trigger('click')
  expect(wrapper.emitted('refreshRequirement')).toEqual([[]])
  await wrapper.setProps({ requirement: { id: 7, revision: 5, system_id: 1, title: '更新后的需求标题' } })
  expect(mocks.create).toHaveBeenCalledTimes(1)
  expect(wrapper.findAll('input')[1].element.value).toBe('人工修改名称')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create.mock.calls[1][0]).toMatchObject({ name: '人工修改名称', requirement_revision: 5 })
  wrapper.unmount()
})

it('requires all association permissions even when creation alone is allowed', async () => {
  useAuthStore().user = { id: 1, permission_codes: ['rd.version.create', 'rd.version.view', 'rd.requirement.view'] } as any
  const wrapper = panel({ id: 7, revision: 4, title: '来源需求' })
  await wrapper.findAll('input')[0].setValue('V1')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('does not report another account\'s pending creation after switching sessions', async () => {
  let finish!: (value: unknown) => void
  mocks.create.mockReturnValue(new Promise(resolve => { finish = resolve }))
  const wrapper = panel({ id: 7, revision: 4, title: '来源需求' })
  await wrapper.findAll('input')[0].setValue('V1')
  await wrapper.get('form').trigger('submit')
  useAuthStore().user = { id: 2, permission_codes: ['*'] } as any
  finish({ id: 9 }); await flushPromises()
  expect(wrapper.emitted('created')).toBeUndefined()
  expect(mocks.success).not.toHaveBeenCalled()
  wrapper.unmount()
})

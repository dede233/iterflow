import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElInput, ElMessageBox } from 'element-plus'
import RequirementCreateView from './RequirementCreateView.vue'

const mocks = vi.hoisted(() => ({ create: vi.fn(), replace: vi.fn(), back: vi.fn(), guards: [] as Array<() => Promise<boolean>> }))
vi.mock('@/api/requirements', () => ({ createRequirement: mocks.create }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: mocks.replace, back: mocks.back }),
  onBeforeRouteLeave: (guard: () => Promise<boolean>) => mocks.guards.push(guard),
}))
const wrappers: ReturnType<typeof mount>[] = []
function view(embedded = true) {
  const wrapper = mount(RequirementCreateView, { props: { embedded }, attachTo: document.body, global: {
    plugins: [ElementPlus],
    stubs: {
      BusinessSystemSelect: true,
      PeopleSelector: { props: ['modelValue'], emits: ['update:modelValue'], template: '<input :value="modelValue[0]" @input="$emit(\'update:modelValue\', $event.target.value ? [Number($event.target.value)] : [])" />' },
      RichTextEditor: { props: ['modelValue', 'disabled'], emits: ['update:modelValue'], template: '<textarea aria-label="需求描述" :disabled="disabled" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
    },
  } })
  wrappers.push(wrapper)
  return wrapper
}
async function valid(wrapper: ReturnType<typeof view>) {
  await wrapper.get('[data-field="title"] input').setValue('清晰的需求标题')
  await wrapper.get('textarea[aria-label="需求描述"]').setValue('<p>需求具体描述</p>')
}
beforeEach(() => { vi.clearAllMocks(); mocks.guards.length = 0; mocks.create.mockReset() })
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.restoreAllMocks() })

it('shows persistent field errors, focuses the first invalid input, and clears errors when corrected', async () => {
  const wrapper = view(); await flushPromises()
  await wrapper.get('form').trigger('submit'); await flushPromises()
  await vi.waitFor(() => expect(wrapper.text()).toContain('标题至少需要 2 个字符'))
  expect(wrapper.text()).toContain('需求描述至少需要 2 个字符')
  expect(document.activeElement).toBe(wrapper.get('[data-field="title"] input').element)
  expect(mocks.create).not.toHaveBeenCalled()
  await valid(wrapper); await flushPromises()
  await vi.waitFor(() => expect(wrapper.text()).not.toContain('至少需要 2 个字符'))
})
it('requires a confirmer and sends only the selected required role when delivery personnel are empty', async () => {
  mocks.create.mockResolvedValue({ id: 41 })
  const wrapper = view(); await flushPromises(); await valid(wrapper)
  const confirmer = wrapper.get('[data-field="confirm"]')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  await vi.waitFor(() => expect(confirmer.text()).toContain('请至少选择一名需求确认人'))
  expect(document.activeElement).toBe(confirmer.get('input').element)
  expect(mocks.create).not.toHaveBeenCalled()
  await confirmer.get('input').setValue('7'); await flushPromises()
  await vi.waitFor(() => expect(confirmer.text()).not.toContain('请至少选择一名需求确认人'))
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ participants: [{ role: 'CONFIRM', user_id: 7 }] }))
})
it('adds selected developers to the existing acceptors in the creation form', async () => {
  mocks.create.mockResolvedValue({ id: 41 })
  const wrapper = view(); await flushPromises(); await valid(wrapper)
  const add = wrapper.findAll('button').find(button => button.text() === '将开发人员加入验收')!
  expect(add.attributes('disabled')).toBeDefined()
  await wrapper.get('[data-field="confirm"] input').setValue('7')
  await wrapper.get('[data-role="DEVELOP"] input').setValue('8')
  await wrapper.get('[data-role="ACCEPT"] input').setValue('9')
  await add.trigger('click')
  expect(add.attributes('disabled')).toBeDefined()
  expect(mocks.create).not.toHaveBeenCalled()

  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(mocks.create).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ participants: [
    { role: 'CONFIRM', user_id: 7 }, { role: 'DEVELOP', user_id: 8 }, { role: 'ACCEPT', user_id: 9 }, { role: 'ACCEPT', user_id: 8 },
  ] }))
})
it('keeps a dirty draft on cancel and route leave until the user confirms', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  const wrapper = view(); await flushPromises(); await valid(wrapper)
  await wrapper.findAll('button').find(button => button.text() === '取消')!.trigger('click'); await flushPromises()
  expect(wrapper.emitted('cancel')).toBeUndefined()
  expect(await mocks.guards[0]!()).toBe(false)
  expect(wrapper.findComponent(ElInput).props('modelValue')).toBe('清晰的需求标题')
  confirm.mockResolvedValue('confirm')
  await wrapper.findAll('button').find(button => button.text() === '取消')!.trigger('click'); await flushPromises()
  expect(wrapper.emitted('cancel')).toEqual([[]])
})
it('expands the same editor without resetting its draft', async () => {
  const wrapper = view(); await flushPromises(); await valid(wrapper)
  const editor = wrapper.get('textarea[aria-label="需求描述"]').element
  await wrapper.findAll('button').find(button => button.text() === '全屏编辑')!.trigger('click')
  expect(wrapper.emitted('expanded')).toEqual([[true]])
  expect(wrapper.get('textarea[aria-label="需求描述"]').element).toBe(editor)
  expect((editor as HTMLTextAreaElement).value).toContain('需求具体描述')
})
it('blocks close and duplicate submissions while saving; successful creation permits navigation', async () => {
  let resolve!: (value: { id: number }) => void
  mocks.create.mockImplementation(() => new Promise(done => { resolve = done }))
  const confirm = vi.spyOn(ElMessageBox, 'confirm')
  const wrapper = view(false); await flushPromises(); await valid(wrapper)
  await wrapper.get('[data-field="confirm"] input').setValue('7')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  await wrapper.get('form').trigger('submit')
  expect(mocks.create).toHaveBeenCalledTimes(1)
  expect(await mocks.guards[0]!()).toBe(false)
  expect(await (wrapper.vm as unknown as { requestClose: () => Promise<boolean> }).requestClose()).toBe(false)
  resolve({ id: 41 }); await flushPromises()
  expect(mocks.replace).toHaveBeenCalledWith('/requirements/41')
  expect(await mocks.guards[0]!()).toBe(true)
  expect(confirm).not.toHaveBeenCalled()
})

import { flushPromises, mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import RichTextEditor from './RichTextEditor.vue'

it('loads a labelled editor and safely applies external content without echoing an update', async () => {
  const wrapper = mount(RichTextEditor, { props: { modelValue: '<p>已有内容</p>', label: '需求范围' } })
  await flushPromises()
  expect(wrapper.find('[role="textbox"]').attributes('aria-label')).toBe('需求范围')
  expect(wrapper.find('[role="textbox"]').text()).toBe('已有内容')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  await wrapper.findAll('button').find(b => b.text() === '链接')!.trigger('click')
  expect(wrapper.find('input').exists()).toBe(true)
  await wrapper.setProps({ modelValue: '<p onclick="attack()">替换内容<script>attack()</script></p>' })
  expect(wrapper.find('input').exists()).toBe(false)
  expect(wrapper.find('[role="textbox"]').text()).toBe('替换内容')
  expect(wrapper.find('[role="textbox"]').html()).not.toContain('onclick')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  wrapper.unmount()
})
it('makes formatting unavailable and closes link input when disabled', async () => {
  const wrapper = mount(RichTextEditor, { props: { modelValue: '<p>测试内容</p>' } })
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text() === '链接')!.trigger('click')
  expect(wrapper.find('input').exists()).toBe(true)
  await wrapper.setProps({ disabled: true })
  expect(wrapper.find('input').exists()).toBe(false)
  expect(wrapper.find('[role="textbox"]').attributes('contenteditable')).toBe('false')
  expect(wrapper.findAll('button').every(b => b.attributes('disabled') !== undefined)).toBe(true)
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  wrapper.unmount()
})
it('rejects unsafe link input before modifying content', async () => {
  const wrapper = mount(RichTextEditor, { props: { modelValue: '<p>测试内容</p>' } })
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text() === '链接')!.trigger('click')
  await wrapper.find('input').setValue('javascript:alert(1)')
  await wrapper.findAll('button').find(b => b.text() === '应用链接')!.trigger('click')
  expect(wrapper.find('[role="alert"]').text()).toContain('完整')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  wrapper.unmount()
})

it('applies toolbar formatting to the actual selected document and emits HTML', async () => {
  const wrapper = mount(RichTextEditor, { props: { modelValue: '<p>测试内容</p>' }, attachTo: document.body })
  await flushPromises()
  const editor = (wrapper.vm as any).editor
  editor.commands.selectAll()
  await wrapper.findAll('button').find(b => b.text() === '加粗')!.trigger('click')
  expect(wrapper.find('[role="textbox"] strong').text()).toBe('测试内容')
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['<p><strong>测试内容</strong></p>'])
  wrapper.unmount()
})

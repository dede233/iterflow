import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import RichTextContent from './RichTextContent.vue'

it('displays legacy markup literally with no active HTML', () => {
  const wrapper = mount(RichTextContent, { props: { content: '<h2>旧内容</h2><img onerror="attack()">' } })
  expect(wrapper.find('h2').exists()).toBe(false)
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.text()).toContain('<h2>旧内容</h2>')
})
it('renders safe formatting while protecting historical unsafe HTML', async () => {
  const wrapper = mount(RichTextContent, { props: { content: '<h2 onclick="attack()">标题</h2><img src=x onerror="attack()"><a href="javascript:attack()">链接</a>', format: 'HTML' } })
  expect(wrapper.find('h2').text()).toBe('标题')
  expect(wrapper.html()).not.toMatch(/onclick|img|javascript|href=/)
  await wrapper.setProps({ format: 'PLAIN' })
  expect(wrapper.find('h2').exists()).toBe(false)
  expect(wrapper.text()).toContain('<h2 onclick=')
})

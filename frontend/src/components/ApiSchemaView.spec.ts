/** @vitest-environment jsdom */
import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import ApiSchemaView from './ApiSchemaView.vue'
import type { OpenApiDocument } from '@/utils/apiDocumentation'

const document: OpenApiDocument = {
  info: { title: '文档', version: '1.8.1' }, paths: {},
  components: { schemas: {
    FeedbackPage: { type: 'object', properties: { items: { title: '数据列表', type: 'array', items: { $ref: '#/components/schemas/Feedback' } } } },
    Feedback: { type: 'object', properties: {
      feedback_no: { title: '反馈编号', type: 'string' },
      owner: { title: '负责人', anyOf: [{ $ref: '#/components/schemas/User' }, { type: 'null' }] },
    } },
    User: { type: 'object', properties: { display_name: { title: '显示名称', type: 'string' } } },
    Loop: { type: 'object', properties: { child: { title: '子对象', $ref: '#/components/schemas/Loop' } } },
  } },
}

it('shows bilingual response fields inside paginated arrays and nullable referenced objects', () => {
  const wrapper = mount(ApiSchemaView, { props: { schema: { $ref: '#/components/schemas/FeedbackPage' }, document }, global: { stubs: { ElTag: true } } })
  expect(wrapper.text()).toContain('items数据列表')
  expect(wrapper.text()).toContain('feedback_no反馈编号')
  expect(wrapper.text()).toContain('display_name显示名称')
  expect(wrapper.findAll('details.nested-fields')).toHaveLength(2)
  wrapper.unmount()
})

it('bounds recursive structures while keeping the complete schema available', () => {
  const wrapper = mount(ApiSchemaView, { props: { schema: { $ref: '#/components/schemas/Loop' }, document }, global: { stubs: { ElTag: true } } })
  expect(wrapper.findAll('.api-schema')).toHaveLength(7)
  expect(wrapper.text()).toContain('查看完整结构')
  wrapper.unmount()
})

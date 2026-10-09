import { describe, expect, it } from 'vitest'
import { documentedOperations, resolveSchema, schemaFields, schemaType } from './apiDocumentation'
import type { OpenApiDocument } from './apiDocumentation'

const document: OpenApiDocument = {
  info: { title: '接口文档', version: '1.8.1' },
  paths: { '/api/v1/feedbacks': { post: { summary: '提交反馈', tags: ['Feedback'] }, get: { summary: '查看反馈' } } },
  components: { schemas: {
    Feedback: { type: 'object', required: ['title'], properties: { title: { type: 'string' }, status: { $ref: '#/components/schemas/Status' } } },
    Status: { type: 'string', enum: ['NEW', 'ACCEPTED'] },
    Loop: { $ref: '#/components/schemas/Loop' },
  } },
}

describe('documentation schema display', () => {
  it('keeps all methods for a shared path and localizes groups', () => {
    const items = documentedOperations(document)
    expect(items.map(item => item.key)).toEqual(['post:/api/v1/feedbacks', 'get:/api/v1/feedbacks'])
    expect(items[0]?.group).toBe('反馈')
  })
  it('resolves references, required fields and enums without changing the schema', () => {
    const fields = schemaFields({ $ref: '#/components/schemas/Feedback' }, document)
    expect(fields[0]).toMatchObject({ name: 'title', label: '', type: 'string', required: true, description: '' })
    expect(fields[1]?.description).toBe('可选值：NEW、ACCEPTED')
    expect(schemaType({ anyOf: [{ type: 'string' }, { type: 'null' }] }, document)).toBe('string / null')
    expect(schemaType({ type: 'array', items: { $ref: '#/components/schemas/Feedback' } }, document)).toBe('Feedback[]')
  })
  it('stops cyclic and external references', () => {
    expect(resolveSchema({ $ref: '#/components/schemas/Loop' }, document)).toEqual({ $ref: '#/components/schemas/Loop' })
    expect(resolveSchema({ $ref: 'https://external.invalid/schema' }, document)).toEqual({ $ref: 'https://external.invalid/schema' })
  })
})

export interface ApiSchema {
  $ref?: string
  type?: string | string[]
  title?: string
  description?: string
  enum?: unknown[]
  default?: unknown
  properties?: Record<string, ApiSchema>
  required?: string[]
  items?: ApiSchema
  anyOf?: ApiSchema[]
  allOf?: ApiSchema[]
  [key: string]: unknown
}
interface ApiParameter { name: string; in: string; required?: boolean; description?: string; schema?: ApiSchema }
export interface ApiOperation {
  summary?: string
  description?: string
  tags?: string[]
  parameters?: ApiParameter[]
  requestBody?: { required?: boolean; content?: Record<string, { schema?: ApiSchema }> }
  responses?: Record<string, { description?: string; content?: Record<string, { schema?: ApiSchema }> }>
  security?: Record<string, string[]>[]
}
export interface OpenApiDocument {
  info: { title: string; version: string; description?: string }
  paths: Record<string, Record<string, ApiOperation>>
  components?: { schemas?: Record<string, ApiSchema> }
  security?: Record<string, string[]>[]
}
export interface DocumentedOperation extends ApiOperation { key: string; path: string; method: string; group: string }
export interface SchemaField { name: string; label: string; type: string; required: boolean; description: string; schema: ApiSchema }

const METHODS = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'])
const GROUPS: Record<string, string> = {
  auth: '登录与账号', dashboard: '工作台', feedback: '反馈', requirement: '需求',
  version: '版本', release: '发布记录', audit: '审计', notification: '通知',
  collaboration: '协作提示', system: '系统管理', file: '附件', docs: '接口文档',
}

export function documentedOperations(document: OpenApiDocument): DocumentedOperation[] {
  return Object.entries(document.paths).flatMap(([path, operations]) =>
    Object.entries(operations).filter(([method]) => METHODS.has(method.toLowerCase())).map(([method, operation]) => ({
      ...operation, path, method: method.toUpperCase(), key: `${method}:${path}`,
      group: GROUPS[(operation.tags?.[0] ?? '').toLowerCase()] ?? operation.tags?.[0] ?? '其他',
    })),
  )
}

export function resolveSchema(schema: ApiSchema | undefined, document: OpenApiDocument, seen = new Set<string>()): ApiSchema {
  if (!schema) return {}
  if (!schema.$ref) return schema
  const prefix = '#/components/schemas/'
  if (!schema.$ref.startsWith(prefix) || seen.has(schema.$ref)) return schema
  const key = schema.$ref.slice(prefix.length).replace(/~1/g, '/').replace(/~0/g, '~')
  const referenced = document.components?.schemas?.[key]
  if (!referenced) return schema
  const next = new Set(seen).add(schema.$ref)
  const { $ref: _ref, ...siblings } = schema
  return { ...resolveSchema(referenced, document, next), ...siblings }
}

export function schemaType(schema: ApiSchema | undefined, document: OpenApiDocument): string {
  const resolved = resolveSchema(schema, document)
  if (resolved.anyOf) return resolved.anyOf.map(item => schemaType(item, document)).join(' / ')
  if (resolved.type === 'array') {
    const item = resolved.items
    return `${item?.$ref?.split('/').at(-1) ?? item?.type ?? '对象'}[]`
  }
  const type = Array.isArray(resolved.type) ? resolved.type.join(' / ') : resolved.type
  return type ?? resolved.$ref?.split('/').at(-1) ?? 'object'
}

export function schemaFields(schema: ApiSchema | undefined, document: OpenApiDocument): SchemaField[] {
  const resolved = resolveSchema(schema, document)
  return Object.entries(resolved.properties ?? {}).map(([name, property]) => {
    const field = resolveSchema(property, document)
    const descriptions = [field.description, field.enum ? `可选值：${field.enum.join('、')}` : undefined]
    return { name, label: field.title && /[\u3400-\u9fff]/.test(field.title) ? field.title : '', schema: property, type: schemaType(property, document), required: resolved.required?.includes(name) ?? false, description: descriptions.filter(Boolean).join('；') }
  })
}

export function schemaBranches(schema: ApiSchema | undefined, document: OpenApiDocument): ApiSchema[] {
  const resolved = resolveSchema(schema, document)
  if (resolved.type === 'array' && resolved.items) return [resolved.items]
  return (resolved.anyOf ?? resolved.allOf ?? []).filter(item => resolveSchema(item, document).type !== 'null')
}

export function hasSchemaChildren(schema: ApiSchema | undefined, document: OpenApiDocument): boolean {
  return schemaFields(schema, document).length > 0 || schemaBranches(schema, document).some(branch => schemaFields(branch, document).length > 0 || resolveSchema(branch, document).type === 'array')
}

export function responseDescription(value?: string): string {
  return value === 'Successful Response' ? '请求成功' : value === 'Validation Error' ? '参数校验失败' : value ?? ''
}

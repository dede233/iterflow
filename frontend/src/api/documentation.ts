import { api } from './client'
import type { OpenApiDocument } from '@/utils/apiDocumentation'

export const getApiDocumentation = () =>
  api.get<OpenApiDocument>('/docs/openapi').then(response => response.data)

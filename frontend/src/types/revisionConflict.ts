import type { components } from './openapi.generated'

export type RevisionConflictData = components['schemas']['RevisionConflictData']
export type ConflictSummaryRow = { label: string; value: string }

export function isRevisionConflict(error: unknown): boolean {
  const response = (error as { response?: { status?: number; data?: { code?: number } } } | null)?.response
  return response?.status === 409 && response.data?.code === 40910
}

export function revisionConflictData(error: unknown): RevisionConflictData | null {
  if (!isRevisionConflict(error)) return null
  const data = (error as { response: { data: { data?: RevisionConflictData } } }).response.data.data
  return data ?? { current_revision: null, current_updated_at: null, current_updated_by: null }
}

export function conflictReadError(error: unknown): string {
  const status = (error as { response?: { status?: number } } | null)?.response?.status
  return status === 403 || status === 404
    ? '该记录已不可访问或不存在'
    : '暂时无法读取服务器版本，请检查网络后重试'
}

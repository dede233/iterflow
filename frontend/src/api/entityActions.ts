import { api } from './client'
import type { components } from '@/types/openapi.generated'

type S = components['schemas']
export type ActionKind = 'requirements' | 'feedbacks'
export type BatchActionResult = S['BatchActionResult']
export type BatchPayload = S['RequirementBatchAction'] | S['FeedbackBatchAction']
const options = { skipRevisionConflictAlert: true, skipForbiddenAlert: true }
export const deleteEntity = (kind: ActionKind, id: number, payload: S['EntityDelete']) =>
  api.delete<S['EntityDeleted']>(`/${kind}/${id}`, { ...options, data: payload }).then(r => r.data)
export const batchActions = (kind: ActionKind, payload: BatchPayload) =>
  api.post<S['BatchActionResponse']>(`/${kind}/batch-actions`, payload, options).then(r => r.data)

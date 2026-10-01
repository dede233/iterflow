import { api } from './client'
import type {
  LinkedFeedback,
  Requirement,
  RequirementCreatePayload,
  RequirementPage,
  RequirementListParams,
  RequirementStatusChangePayload,
  RequirementUpdatePayload,
} from '@/types/domain'

export const listRequirements = (params: RequirementListParams = {}) =>
  api.get<RequirementPage>('/requirements', { params }).then((r) => r.data)

export const getRequirement = (id: number) =>
  api.get<Requirement>(`/requirements/${id}`).then((r) => r.data)

export const listRequirementFeedbacks = (id: number) =>
  api.get<LinkedFeedback[]>(`/requirements/${id}/feedbacks`).then((r) => r.data)

export const createRequirement = (payload: RequirementCreatePayload) =>
  api.post<Requirement>('/requirements', payload).then((r) => r.data)

export const updateRequirement = (id: number, payload: RequirementUpdatePayload) =>
  api.patch<Requirement>(`/requirements/${id}`, payload, { skipRevisionConflictAlert: true }).then((r) => r.data)

export const changeRequirementStatus = (
  id: number,
  status: RequirementStatusChangePayload['status'],
  revision: number,
  reason?: string | null,
) =>
  api
    .patch<Requirement>(`/requirements/${id}/status`, { status, revision, reason: reason ?? null }, { skipRevisionConflictAlert: true })
    .then((r) => r.data)

import { api } from './client'
import type {
  LinkedFeedback,
  Requirement,
  RequirementCreatePayload,
  RequirementPage,
  RequirementStatusChangePayload,
  RequirementUpdatePayload,
} from '@/types/domain'

export const listRequirements = (params: { page?: number; page_size?: number } = {}) =>
  api.get<RequirementPage>('/requirements', { params }).then((r) => r.data)

export const getRequirement = (id: number) =>
  api.get<Requirement>(`/requirements/${id}`).then((r) => r.data)

export const listRequirementFeedbacks = (id: number) =>
  api.get<LinkedFeedback[]>(`/requirements/${id}/feedbacks`).then((r) => r.data)

export const createRequirement = (payload: RequirementCreatePayload) =>
  api.post<Requirement>('/requirements', payload).then((r) => r.data)

export const updateRequirement = (id: number, payload: RequirementUpdatePayload) =>
  api.patch<Requirement>(`/requirements/${id}`, payload).then((r) => r.data)

export const changeRequirementStatus = (
  id: number,
  status: RequirementStatusChangePayload['status'],
  revision: number,
  reason?: string | null,
) =>
  api
    .patch<Requirement>(`/requirements/${id}/status`, { status, revision, reason: reason ?? null })
    .then((r) => r.data)

import { withDescriptionImages } from '@/utils/requirementImages'
import { api } from './client'
import type {
  Feedback,
  LinkedFeedback,
  Requirement,
  RequirementCreatePayload,
  RequirementPage,
  RequirementListParams,
  RequirementStatusChangePayload,
  RequirementUpdatePayload,
} from '@/types/domain'
import type { components } from '@/types/openapi.generated'

type OnlineReview = components['schemas']['OnlineReviewOut']
const onlineReviewWriteOptions = { skipConflictAlert: true, skipForbiddenAlert: true }

export const listRequirements = (params: RequirementListParams = {}) =>
  api.get<RequirementPage>('/requirements', { params }).then((r) => r.data)

export const getRequirement = (id: number) =>
  api.get<Requirement>(`/requirements/${id}`).then((r) => r.data)

export const listRequirementFeedbacks = (id: number) =>
  api.get<LinkedFeedback[]>(`/requirements/${id}/feedbacks`).then((r) => r.data)

export const getOnlineReview = (id: number, page = 1) =>
  api.get<OnlineReview>(`/requirements/${id}/online-review`, { params: { page } }).then((r) => r.data)

export const confirmOnlineReview = (id: number, payload: components['schemas']['OnlineReviewConfirm']) =>
  api.post<components['schemas']['OnlineReviewConfirmation']>(`/requirements/${id}/online-review/confirm`, payload, onlineReviewWriteOptions).then((r) => r.data)

export const createOnlineReviewFeedback = (id: number, payload: components['schemas']['OnlineReviewFeedbackCreate']) =>
  api.post<Feedback>(`/requirements/${id}/online-review/feedbacks`, payload, onlineReviewWriteOptions).then((r) => r.data)

export const createRequirement = async (payload: RequirementCreatePayload) =>
  api.post<Requirement>('/requirements', await withDescriptionImages(payload)).then((r) => r.data)

export const updateRequirement = async (id: number, payload: RequirementUpdatePayload) =>
  api.patch<Requirement>(`/requirements/${id}`, await withDescriptionImages(payload), { skipRevisionConflictAlert: true }).then((r) => r.data)

export const changeRequirementStatus = (
  id: number,
  status: RequirementStatusChangePayload['status'],
  revision: number,
  reason?: string | null,
) =>
  api
    .patch<Requirement>(`/requirements/${id}/status`, { status, revision, reason: reason ?? null }, { skipRevisionConflictAlert: true, skipForbiddenAlert: true })
    .then((r) => r.data)

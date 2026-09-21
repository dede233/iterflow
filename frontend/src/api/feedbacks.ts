import { api } from './client'
import type {
  Feedback,
  FeedbackCreatePayload,
  FeedbackListParams,
  FeedbackStatusChangePayload,
  FeedbackUpdatePayload,
  PageResult,
} from '@/types/domain'

export const listFeedbacks = (params: FeedbackListParams = {}) =>
  api.get<PageResult<Feedback>>('/feedbacks', { params }).then((r) => r.data)

export const getFeedback = (id: number) =>
  api.get<Feedback>(`/feedbacks/${id}`).then((r) => r.data)

export const createFeedback = (payload: FeedbackCreatePayload) =>
  api.post<Feedback>('/feedbacks', payload).then((r) => r.data)

export const updateFeedback = (id: number, payload: FeedbackUpdatePayload) =>
  api.patch<Feedback>(`/feedbacks/${id}`, payload).then((r) => r.data)

export const changeFeedbackStatus = (id: number, payload: FeedbackStatusChangePayload) =>
  api.patch<Feedback>(`/feedbacks/${id}/status`, payload).then((r) => r.data)

export const convertFeedback = (id: number, payload: unknown) =>
  api.post(`/feedbacks/${id}/convert`, payload).then((r) => r.data)

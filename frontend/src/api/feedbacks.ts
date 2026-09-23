import { api } from './client'
import type {
  AttachmentItem,
  CommentItem,
  ConvertFeedbackPayload,
  Feedback,
  FeedbackCreatePayload,
  FeedbackListParams,
  FeedbackPage,
  FeedbackStatusChangePayload,
  FeedbackUpdatePayload,
  Requirement,
} from '@/types/domain'

export const listFeedbacks = (params: FeedbackListParams = {}) =>
  api.get<FeedbackPage>('/feedbacks', { params }).then((r) => r.data)

export const getFeedback = (id: number) =>
  api.get<Feedback>(`/feedbacks/${id}`).then((r) => r.data)

export const createFeedback = (payload: FeedbackCreatePayload) =>
  api.post<Feedback>('/feedbacks', payload).then((r) => r.data)

export const updateFeedback = (id: number, payload: FeedbackUpdatePayload) =>
  api.patch<Feedback>(`/feedbacks/${id}`, payload).then((r) => r.data)

export const changeFeedbackStatus = (id: number, payload: FeedbackStatusChangePayload) =>
  api.patch<Feedback>(`/feedbacks/${id}/status`, payload).then((r) => r.data)

export const convertFeedback = (id: number, payload: ConvertFeedbackPayload) =>
  api.post<Requirement>(`/feedbacks/${id}/convert`, payload).then((r) => r.data)

// --- attachments (business relation stores file_id only) ---
export const listFeedbackAttachments = (id: number) =>
  api.get<AttachmentItem[]>(`/feedbacks/${id}/attachments`).then((r) => r.data)

export const uploadFeedbackAttachment = (id: number, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<AttachmentItem>(`/feedbacks/${id}/attachments`, form, { timeout: 120000 }).then((r) => r.data)
}

// Download goes through the authenticated axios client (Authorization header),
// not a bare href, so feedback-scope authorization is enforced.
export const downloadFeedbackAttachment = (id: number, fileId: number) =>
  api
    .get(`/feedbacks/${id}/attachments/${fileId}/download`, { responseType: 'blob' })
    .then((r) => r.data as Blob)

// --- comments ---
export const listFeedbackComments = (id: number) =>
  api.get<CommentItem[]>(`/feedbacks/${id}/comments`).then((r) => r.data)

export const createFeedbackComment = (id: number, content: string) =>
  api.post<CommentItem>(`/feedbacks/${id}/comments`, { content }).then((r) => r.data)

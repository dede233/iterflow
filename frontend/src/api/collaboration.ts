import { api } from './client'
import type { components } from '@/types/openapi.generated'
export type Person = components['schemas']['PersonOption']
export type Participant = components['schemas']['ParticipantInput']
export type Participants = components['schemas']['ParticipantsOut']
export type FeedbackCollaboration = components['schemas']['FeedbackCollaborationOut']
export const listPeople = (kind: 'feedback' | 'requirement', keyword = '', page = 1, feedback_id?: number) =>
  api.get<components['schemas']['PersonPage']>('/collaboration/people', { params: { kind, keyword, page, page_size: 20, feedback_id } }).then(r => r.data)
export const getFeedbackCollaboration = (id: number) => api.get<FeedbackCollaboration>(`/feedbacks/${id}/collaboration`).then(r => r.data)
export const setRecipients = (id: number, revision: number, recipient_ids: number[]) => api.put<FeedbackCollaboration>(`/feedbacks/${id}/recipients`, { revision, recipient_ids }).then(r => r.data)
export const transferFeedback = (id: number, revision: number, handler_id: number, reason: string) => api.post<FeedbackCollaboration>(`/feedbacks/${id}/transfer`, { revision, handler_id, reason }).then(r => r.data)
export const getParticipants = (id: number) => api.get<Participants>(`/requirements/${id}/participants`).then(r => r.data)
export const setParticipants = (id: number, revision: number, participants: Participant[]) => api.put<Participants>(`/requirements/${id}/participants`, { revision, participants }).then(r => r.data)

export type Workflow = components['schemas']['WorkflowOut']
export type WorkflowAction = components['schemas']['WorkflowAction']
export const getWorkflow = (id: number) => api.get<Workflow>(`/requirements/${id}/workflow`).then(r => r.data)
export const actWorkflow = (id: number, payload: WorkflowAction) => api.post<Workflow>(`/requirements/${id}/workflow`, payload).then(r => r.data)

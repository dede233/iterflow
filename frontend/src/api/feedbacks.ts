import { api } from './client'
import type { Feedback, PageResult } from '@/types/domain'
export const listFeedbacks = (params={}) => api.get<PageResult<Feedback>>('/feedbacks', {params}).then(r=>r.data)
export const getFeedback = (id:number) => api.get<Feedback>(`/feedbacks/${id}`).then(r=>r.data)
export const createFeedback = (payload:any) => api.post('/feedbacks', payload).then(r=>r.data)
export const updateFeedback = (id:number,payload:any) => api.patch(`/feedbacks/${id}`,payload).then(r=>r.data)
export const convertFeedback = (id:number,payload:any) => api.post(`/feedbacks/${id}/convert`,payload).then(r=>r.data)

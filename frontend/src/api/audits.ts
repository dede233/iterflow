import { api } from './client'
import type { AuditItem, AuditListParams, AuditPage } from '@/types/domain'

export const listAudits = (params: AuditListParams = {}) =>
  api.get<AuditPage>('/audits', { params }).then((response) => response.data)

export const getAudit = (id: number) =>
  api.get<AuditItem>(`/audits/${id}`).then((response) => response.data)

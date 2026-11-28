import { api } from './client'
import type { paths } from '@/types/openapi.generated'

type MailDeliveryMonitor = paths['/admin/mail-delivery-monitor']['get']
type MonitorParams = NonNullable<MailDeliveryMonitor['parameters']['query']>
type MailDeliveryPage = MailDeliveryMonitor['responses'][200]['content']['application/json']
export type MailDeliveryDetail = paths['/admin/mail-delivery-monitor/{delivery_id}']['get']['responses'][200]['content']['application/json']
type RetryPayload = paths['/admin/mail-deliveries/{delivery_id}/retry']['post']['requestBody']['content']['application/json']
type ResendPayload = paths['/admin/mail-delivery-monitor/{delivery_id}/resend']['post']['requestBody']['content']['application/json']
type RecipientLookup = paths['/admin/mail-delivery-monitor/recipients']['get']
type RecipientParams = NonNullable<RecipientLookup['parameters']['query']>
type RecipientPage = RecipientLookup['responses'][200]['content']['application/json']

export const listMailDeliveryMonitor = (params: MonitorParams) =>
  api.get<MailDeliveryPage>('/admin/mail-delivery-monitor', { params, skipForbiddenAlert: true }).then(response => response.data)

export const getMailDeliveryDetail = (id: string, signal: AbortSignal) =>
  api.get<MailDeliveryDetail>(`/admin/mail-delivery-monitor/${encodeURIComponent(id)}`, { signal, skipForbiddenAlert: true }).then(response => response.data)

export const listMailDeliveryRecipients = (params: RecipientParams) =>
  api.get<RecipientPage>('/admin/mail-delivery-monitor/recipients', { params, skipForbiddenAlert: true }).then(response => response.data)

export async function retryMailDelivery(id: string, payload: RetryPayload): Promise<void> {
  await api.post(`/admin/mail-deliveries/${encodeURIComponent(id)}/retry`, payload, { skipConflictAlert: true })
}

export async function resendMailDelivery(id: string, payload: ResendPayload): Promise<void> {
  await api.post(`/admin/mail-delivery-monitor/${encodeURIComponent(id)}/resend`, payload, { skipConflictAlert: true })
}

import { api } from './client'

export type EditingEntityType = 'FEEDBACK' | 'REQUIREMENT' | 'VERSION'

export interface ExistingEditor {
  user_id: number
  display_name: string
  active_at: string
}

export interface EditingStartResponse {
  existing_editor: ExistingEditor | null
}

export interface EditingHeartbeatResponse {
  ok: boolean
  existing_editor: ExistingEditor | null
}

export interface EditingEndResponse {
  ok: boolean
}

const payload = (entity_type: EditingEntityType, entity_id: number) => ({ entity_type, entity_id })

export const startEditing = (entity_type: EditingEntityType, entity_id: number) =>
  api.post<EditingStartResponse>('/editing/start', payload(entity_type, entity_id)).then((r) => r.data)

export const editingHeartbeat = (entity_type: EditingEntityType, entity_id: number) =>
  api.post<EditingHeartbeatResponse>('/editing/heartbeat', payload(entity_type, entity_id)).then((r) => r.data)

export const endEditing = (entity_type: EditingEntityType, entity_id: number) =>
  api.post<EditingEndResponse>('/editing/end', payload(entity_type, entity_id)).then((r) => r.data)

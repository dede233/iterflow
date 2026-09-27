import { api } from './client'
import type {
  BusinessModuleCreatePayload,
  BusinessModuleItem,
  BusinessModuleUpdatePayload,
  BusinessSystemCreatePayload,
  BusinessSystemItem,
  BusinessSystemUpdatePayload,
  SystemsResponse,
} from '@/types/domain'

// Requires sys.system.view or sys.system.manage; callers should guard on either
// permission to avoid a 403 toast for users without catalog access.
export const listSystems = () =>
  api.get<SystemsResponse>('/systems').then((r) => r.data)

export const listManagedSystems = () =>
  api.get<SystemsResponse>('/systems/manage').then((r) => r.data)

export const createSystem = (payload: BusinessSystemCreatePayload) =>
  api.post<BusinessSystemItem>('/systems', payload).then((r) => r.data)

export const updateSystem = (id: number, payload: BusinessSystemUpdatePayload) =>
  api.patch<BusinessSystemItem>(`/systems/${id}`, payload).then((r) => r.data)

export const createModule = (systemId: number, payload: BusinessModuleCreatePayload) =>
  api.post<BusinessModuleItem>(`/systems/${systemId}/modules`, payload).then((r) => r.data)

export const updateModule = (id: number, payload: BusinessModuleUpdatePayload) =>
  api.patch<BusinessModuleItem>(`/systems/modules/${id}`, payload).then((r) => r.data)

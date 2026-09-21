import { api } from './client'
import type { BusinessModuleItem, BusinessSystemItem } from '@/types/domain'

export interface SystemsResponse {
  systems: BusinessSystemItem[]
  modules: BusinessModuleItem[]
}

// Requires the sys.system.view permission; callers should guard on it so users
// without it (e.g. plain members) don't trigger a 403 toast.
export const listSystems = () =>
  api.get<SystemsResponse>('/systems').then((r) => r.data)

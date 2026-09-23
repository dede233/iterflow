import { api } from './client'
import type { SystemsResponse } from '@/types/domain'

// Requires the sys.system.view permission; callers should guard on it so users
// without it (e.g. plain members) don't trigger a 403 toast.
export const listSystems = () =>
  api.get<SystemsResponse>('/systems').then((r) => r.data)

import { api } from './client'
import type { ReleasePage, ReleaseItem, ReleaseListParams } from '@/types/domain'

export const listReleases = (params: ReleaseListParams = {}) =>
  api.get<ReleasePage>('/releases', { params }).then((r) => r.data)

export const getRelease = (id: number) =>
  api.get<ReleaseItem>(`/releases/${id}`).then((r) => r.data)

import { api } from './client'
import type { ReleasePage, ReleaseItem } from '@/types/domain'

export const listReleases = (params: { page?: number; page_size?: number; version_id?: number } = {}) =>
  api.get<ReleasePage>('/releases', { params }).then((r) => r.data)

export const getRelease = (id: number) =>
  api.get<ReleaseItem>(`/releases/${id}`).then((r) => r.data)

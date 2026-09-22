import { api } from './client'
import type {
  PageResult,
  VersionCreatePayload,
  VersionItem,
  VersionRequirementsResult,
  VersionUpdatePayload,
} from '@/types/domain'

export const listVersions = (params: { page?: number; page_size?: number } = {}) =>
  api.get<PageResult<VersionItem>>('/versions', { params }).then((r) => r.data)

export const getVersion = (id: number) =>
  api.get<VersionItem>(`/versions/${id}`).then((r) => r.data)

export const createVersion = (payload: VersionCreatePayload) =>
  api.post<VersionItem>('/versions', payload).then((r) => r.data)

export const updateVersion = (id: number, payload: VersionUpdatePayload) =>
  api.patch<VersionItem>(`/versions/${id}`, payload).then((r) => r.data)

export const changeVersionStatus = (
  id: number,
  status: string,
  revision: number,
  reason?: string | null,
) =>
  api
    .patch<VersionItem>(`/versions/${id}/status`, { status, revision, reason: reason ?? null })
    .then((r) => r.data)

// --- version <-> requirement relationship ---
export const listVersionRequirements = (id: number) =>
  api.get<VersionRequirementsResult>(`/versions/${id}/requirements`).then((r) => r.data)

export const addVersionRequirement = (id: number, requirementId: number, revision: number) =>
  api
    .post<VersionItem>(`/versions/${id}/requirements`, {
      requirement_id: requirementId,
      revision,
    })
    .then((r) => r.data)

export const moveVersionRequirement = (
  targetVersionId: number,
  requirementId: number,
  revision: number,
  reason: string,
) =>
  api
    .post<VersionItem>(`/versions/${targetVersionId}/requirements/move`, {
      requirement_id: requirementId,
      revision,
      reason,
    })
    .then((r) => r.data)

export const removeVersionRequirement = (
  id: number,
  requirementId: number,
  revision: number,
  reason?: string | null,
) =>
  api
    .delete<VersionItem>(`/versions/${id}/requirements/${requirementId}`, {
      data: { revision, reason: reason ?? null },
    })
    .then((r) => r.data)

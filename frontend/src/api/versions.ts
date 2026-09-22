import { api } from './client'
import type {
  PageResult,
  PublishCheckResult,
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

export const addVersionRequirement = (
  id: number,
  requirementId: number,
  revision: number,
  versionRevision: number,
) =>
  api
    .post<VersionItem>(`/versions/${id}/requirements`, {
      requirement_id: requirementId,
      revision,
      version_revision: versionRevision,
    })
    .then((r) => r.data)

export const moveVersionRequirement = (
  targetVersionId: number,
  requirementId: number,
  revision: number,
  versionRevision: number,
  reason: string,
) =>
  api
    .post<VersionItem>(`/versions/${targetVersionId}/requirements/move`, {
      requirement_id: requirementId,
      revision,
      version_revision: versionRevision,
      reason,
    })
    .then((r) => r.data)

export const removeVersionRequirement = (
  id: number,
  requirementId: number,
  revision: number,
  versionRevision: number,
  reason?: string | null,
) =>
  api
    .delete<VersionItem>(`/versions/${id}/requirements/${requirementId}`, {
      data: { revision, version_revision: versionRevision, reason: reason ?? null },
    })
    .then((r) => r.data)

export interface PublishResult {
  release: { id: number; version_id: number; result: string; released_at: string }
  version_id: number
  released_requirement_ids: number[]
  online_feedback_ids: number[]
}

// Pre-publish check preview: 200 with {passed:true,...} when publishable, 409
// (checks in error body) otherwise. skipConflictAlert keeps the global 409
// dialog from firing so the caller can render the checklist inline.
export const checkVersionPublish = (id: number) =>
  api
    .post<PublishCheckResult>(`/versions/${id}/publish/check`, undefined, { skipConflictAlert: true })
    .then((r) => r.data)

// Publish is the single release entry point (VersionService.publish). It flips
// the READY version to RELEASED and syncs requirement/feedback online status.
export const publishVersion = (id: number, releaseNotes: string, revision: number) =>
  api
    .post<PublishResult>(`/versions/${id}/publish`, {
      released_at: new Date().toISOString(),
      release_notes: releaseNotes,
      revision,
    })
    .then((r) => r.data)

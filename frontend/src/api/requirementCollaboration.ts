import { api } from './client'
import type { components } from '@/types/openapi.generated'
export type AssigneeOption = components['schemas']['AssigneeOption']
export type Collaborators = components['schemas']['RequirementCollaboratorsOut']
export type CollaboratorsUpdate = components['schemas']['RequirementCollaboratorsUpdate']
export type AssigneeKind = 'OWNER' | 'DEVELOPER' | 'DESIGNER'
export const getCollaborators = (id: number) =>
  api.get<Collaborators>(`/requirements/${id}/collaborators`).then(r => r.data)
export const replaceCollaborators = (id: number, payload: CollaboratorsUpdate) =>
  api.put<Collaborators>(`/requirements/${id}/collaborators`, payload, { skipRevisionConflictAlert: true }).then(r => r.data)
export const listAssigneeOptions = (kind: AssigneeKind, keyword = '', page = 1) =>
  api.get<components['schemas']['AssigneeOptionsPage']>('/requirements/assignee-options', { params: { kind, keyword, page } }).then(r => r.data)
export const updateCollaboratorGroup = (id: number, payload: components['schemas']['RequirementCollaboratorGroupUpdate']) =>
  api.patch<Collaborators>(`/requirements/${id}/collaborators`, payload, { skipRevisionConflictAlert: true }).then(r => r.data)
export const startRequirementStage = (id: number, payload: components['schemas']['RequirementStageStart']) =>
  api.post<components['schemas']['RequirementOut']>(`/requirements/${id}/start-stage`, payload, { skipRevisionConflictAlert: true }).then(r => r.data)

export const confirmDevelopmentCompletion = (id: number, revision: number) =>
  api.post<Collaborators>(`/requirements/${id}/development-completion`, { revision }, { skipRevisionConflictAlert: true }).then(r => r.data)

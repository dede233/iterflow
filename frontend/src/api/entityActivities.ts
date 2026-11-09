import { api } from './client'
import type { EntityActivity } from '@/types/domain'

export type ActivityKind = 'feedback' | 'requirement' | 'version'
const resources = { feedback: 'feedbacks', requirement: 'requirements', version: 'versions' } as const

export const listEntityActivities = (kind: ActivityKind, id: number) =>
  api.get<EntityActivity[]>(`/${resources[kind]}/${id}/activities`, { skipForbiddenAlert: true }).then(response => response.data)

// Progress is derived from requirements; cancellation remains a version action.
// Backend stays the source of truth for progress and publish readiness.

import type { components } from '@/types/openapi.generated'

export const VERSION_STATUSES = [
  { value: 'PLANNING', label: '规划中' },
  { value: 'DEVELOPING', label: '开发中' },
  { value: 'TESTING', label: '测试中' },
  { value: 'READY', label: '待发布' },
  { value: 'RELEASED', label: '已发布' },
  { value: 'CANCELED', label: '已取消' },
] as const

export const versionStatusLabel = Object.fromEntries(
  VERSION_STATUSES.map((i) => [i.value, i.label]),
) as Record<string, string>

// Version states in which the requirement set is frozen.
export const FROZEN_VERSION_STATES = new Set(['RELEASED', 'CANCELED'])

export function versionRequirementSetFrozen(status: string): boolean {
  return FROZEN_VERSION_STATES.has(status)
}

export interface VersionStatusAction {
  target: components['schemas']['ManualVersionStatus']
  label: string
  needsReason: boolean
}

export function availableVersionStatusActions(
  status: string,
  canChange: boolean,
): VersionStatusAction[] {
  if (!canChange || !['PLANNING', 'DEVELOPING', 'TESTING', 'READY'].includes(status)) return []
  return [{ target: 'CANCELED', label: '取消版本', needsReason: false }]
}

export function versionStatusTagType(status: string): string {
  return (
    {
      PLANNING: 'info',
      DEVELOPING: 'primary',
      TESTING: 'warning',
      READY: 'warning',
      RELEASED: 'success',
      CANCELED: 'info',
    }[status] ?? ''
  )
}

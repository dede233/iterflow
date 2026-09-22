// Version vocabulary + human-driven state machine (frontend mirror of the
// backend VERSION_TRANSITIONS). Backend stays the source of truth.

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
export const FROZEN_VERSION_STATES = new Set(['READY', 'RELEASED', 'CANCELED'])

export function versionRequirementSetFrozen(status: string): boolean {
  return FROZEN_VERSION_STATES.has(status)
}

export interface VersionStatusAction {
  target: string
  label: string
  needsReason: boolean
}

const TRANSITIONS: Record<string, VersionStatusAction[]> = {
  PLANNING: [
    { target: 'DEVELOPING', label: '开始开发', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  DEVELOPING: [
    { target: 'TESTING', label: '提测', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  TESTING: [
    { target: 'DEVELOPING', label: '退回开发', needsReason: false },
    { target: 'READY', label: '待发布', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  READY: [{ target: 'TESTING', label: '退回测试', needsReason: true }],
}

export function availableVersionStatusActions(
  status: string,
  canChange: boolean,
): VersionStatusAction[] {
  if (!canChange) return []
  return TRANSITIONS[status] ?? []
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

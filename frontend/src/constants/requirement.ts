// Requirement vocabulary + human-driven state machine (frontend mirror of the
// backend ALLOWED_TRANSITIONS). Backend stays the source of truth; these tables
// only drive labels and which status buttons to render.

import type { components } from '@/types/openapi.generated'

export type RequirementPriority = components['schemas']['Priority']
export type ManualRequirementStatus = components['schemas']['ManualRequirementStatus']

export const REQUIREMENT_PRIORITIES = [
  { value: 'P0', label: 'P0' },
  { value: 'P1', label: 'P1' },
  { value: 'P2', label: 'P2' },
  { value: 'P3', label: 'P3' },
  { value: 'P4', label: 'P4' },
] as const

// requirement_type is a free uppercase token on the backend; these are common presets.
export const REQUIREMENT_TYPES = [
  { value: 'FEATURE', label: '新功能' },
  { value: 'OPTIMIZATION', label: '功能优化' },
  { value: 'BUG', label: '缺陷修复' },
  { value: 'TECH', label: '技术改造' },
  { value: 'OTHER', label: '其他' },
] as const

export const REQUIREMENT_STATUSES = [
  { value: 'DRAFT', label: '待确认' },
  { value: 'CONFIRMED', label: '待开发' },
  { value: 'DEVELOPING', label: '开发中' },
  { value: 'TESTING', label: '待验收' },
  { value: 'DONE', label: '待发布' },
  { value: 'ONLINE', label: '已上线' },
  { value: 'PAUSED', label: '已暂停' },
  { value: 'CANCELED', label: '已取消' },
] as const

const label = (list: readonly { value: string; label: string }[]) =>
  Object.fromEntries(list.map((i) => [i.value, i.label])) as Record<string, string>

export const requirementStatusLabel = label(REQUIREMENT_STATUSES)
export const requirementTypeLabel = label(REQUIREMENT_TYPES)

export interface ReqStatusAction {
  target: ManualRequirementStatus
  label: string
  needsReason: boolean
}

// Human-settable transitions keyed by current status (mirrors backend).
const TRANSITIONS: Record<string, ReqStatusAction[]> = {
  DRAFT: [
    { target: 'CONFIRMED', label: '确认', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: true },
  ],
  CONFIRMED: [
    { target: 'DEVELOPING', label: '开始开发', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: true },
    { target: 'CANCELED', label: '取消', needsReason: true },
  ],
  DEVELOPING: [
    { target: 'TESTING', label: '提交验收', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: true },
  ],
  TESTING: [
    { target: 'DEVELOPING', label: '退回开发', needsReason: true },
    { target: 'DONE', label: '验收通过', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: true },
  ],
  DONE: [{ target: 'DEVELOPING', label: '重新开发', needsReason: true }],
  PAUSED: [
    { target: 'CONFIRMED', label: '恢复待开发', needsReason: true },
    { target: 'DEVELOPING', label: '恢复开发', needsReason: true },
    { target: 'CANCELED', label: '取消', needsReason: true },
  ],
}

export function availableRequirementStatusActions(
  status: string,
  canChange: boolean,
): ReqStatusAction[] {
  if (!canChange) return []
  return TRANSITIONS[status] ?? []
}

export function requirementStatusTagType(status: string): string {
  return (
    {
      DRAFT: 'info',
      CONFIRMED: 'primary',
      PLANNED: 'primary',
      DEVELOPING: 'primary',
      TESTING: 'warning',
      DONE: 'success',
      ONLINE: 'success',
      PAUSED: 'warning',
      CANCELED: 'info',
    }[status] ?? ''
  )
}

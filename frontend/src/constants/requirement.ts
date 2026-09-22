// Requirement vocabulary + human-driven state machine (frontend mirror of the
// backend ALLOWED_TRANSITIONS). Backend stays the source of truth; these tables
// only drive labels and which status buttons to render.

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
  { value: 'DRAFT', label: '草稿' },
  { value: 'CONFIRMED', label: '已确认' },
  { value: 'PLANNED', label: '已排期' },
  { value: 'DEVELOPING', label: '开发中' },
  { value: 'TESTING', label: '测试中' },
  { value: 'DONE', label: '已完成' },
  { value: 'ONLINE', label: '已上线' },
  { value: 'PAUSED', label: '已暂停' },
  { value: 'CANCELED', label: '已取消' },
] as const

const label = (list: readonly { value: string; label: string }[]) =>
  Object.fromEntries(list.map((i) => [i.value, i.label])) as Record<string, string>

export const requirementStatusLabel = label(REQUIREMENT_STATUSES)
export const requirementTypeLabel = label(REQUIREMENT_TYPES)

export interface ReqStatusAction {
  target: string
  label: string
  needsReason: boolean
}

// Human-settable transitions keyed by current status (mirrors backend).
const TRANSITIONS: Record<string, ReqStatusAction[]> = {
  DRAFT: [
    { target: 'CONFIRMED', label: '确认', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  CONFIRMED: [
    { target: 'PLANNED', label: '排期', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  PLANNED: [
    { target: 'DEVELOPING', label: '开始开发', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
  ],
  DEVELOPING: [
    { target: 'TESTING', label: '提测', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: false },
  ],
  TESTING: [
    { target: 'DEVELOPING', label: '退回开发', needsReason: false },
    { target: 'DONE', label: '完成', needsReason: false },
    { target: 'PAUSED', label: '暂停', needsReason: false },
  ],
  DONE: [{ target: 'DEVELOPING', label: '重新开发', needsReason: true }],
  PAUSED: [
    { target: 'CONFIRMED', label: '恢复到已确认', needsReason: false },
    { target: 'PLANNED', label: '恢复到已排期', needsReason: false },
    { target: 'DEVELOPING', label: '恢复开发', needsReason: false },
    { target: 'CANCELED', label: '取消', needsReason: false },
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

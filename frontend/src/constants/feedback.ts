// Frozen V1.5 Feedback vocabulary + human-driven state machine (frontend mirror
// of the backend policy). The backend remains the source of truth: these tables
// only drive labels and which action buttons to render. Any rejected transition
// still comes back as a 409 from the API.

export type ManualFeedbackStatus = 'NEW' | 'ACCEPTED' | 'DUPLICATE' | 'CANNOT_REPRODUCE' | 'CLOSED'

export const FEEDBACK_TYPES = [
  { value: 'NEW_FEATURE', label: '新功能' },
  { value: 'FEATURE_OPTIMIZATION', label: '功能优化' },
  { value: 'SYSTEM_ISSUE', label: '系统问题' },
  { value: 'DATA_ISSUE', label: '数据问题' },
  { value: 'UI_UX', label: 'UI体验问题' },
  { value: 'OTHER', label: '其他' },
] as const

export const FEEDBACK_URGENCIES = [
  { value: 'NORMAL', label: '普通' },
  { value: 'URGENT', label: '较急' },
  { value: 'CRITICAL', label: '紧急' },
] as const

// Full FeedbackStatus (includes downstream statuses used only for filtering/display).
export const FEEDBACK_STATUSES = [
  { value: 'NEW', label: '待处理' },
  { value: 'ACCEPTED', label: '已受理' },
  { value: 'REQUIREMENT_LINKED', label: '已转需求' },
  { value: 'PLANNED', label: '已排期' },
  { value: 'DEVELOPING', label: '开发中' },
  { value: 'TESTING', label: '测试中' },
  { value: 'ONLINE', label: '已上线' },
  { value: 'DUPLICATE', label: '重复' },
  { value: 'CANNOT_REPRODUCE', label: '无法复现' },
  { value: 'CLOSED', label: '已关闭' },
] as const

const label = (list: readonly { value: string; label: string }[]) =>
  Object.fromEntries(list.map((i) => [i.value, i.label])) as Record<string, string>

export const feedbackTypeLabel = label(FEEDBACK_TYPES)
export const feedbackUrgencyLabel = label(FEEDBACK_URGENCIES)
export const feedbackStatusLabel = label(FEEDBACK_STATUSES)

export interface StatusAction {
  target: ManualFeedbackStatus
  label: string
  needsReason: boolean
  needsDuplicate: boolean
}

// Human-settable transitions, keyed by the current status. Mirrors the backend
// ALLOWED_TRANSITIONS. Downstream statuses expose no manual action.
const TRANSITIONS: Record<string, StatusAction[]> = {
  NEW: [
    { target: 'ACCEPTED', label: '受理', needsReason: false, needsDuplicate: false },
    { target: 'DUPLICATE', label: '标记重复', needsReason: false, needsDuplicate: true },
    { target: 'CANNOT_REPRODUCE', label: '无法复现', needsReason: true, needsDuplicate: false },
    { target: 'CLOSED', label: '关闭', needsReason: true, needsDuplicate: false },
  ],
  ACCEPTED: [
    { target: 'DUPLICATE', label: '标记重复', needsReason: false, needsDuplicate: true },
    { target: 'CANNOT_REPRODUCE', label: '无法复现', needsReason: true, needsDuplicate: false },
    { target: 'CLOSED', label: '关闭', needsReason: true, needsDuplicate: false },
  ],
  DUPLICATE: [{ target: 'NEW', label: '重开', needsReason: true, needsDuplicate: false }],
  CANNOT_REPRODUCE: [{ target: 'NEW', label: '重开', needsReason: true, needsDuplicate: false }],
  CLOSED: [{ target: 'NEW', label: '重开', needsReason: true, needsDuplicate: false }],
}

/** Status actions to render, given the current status and whether the user may edit. */
export function availableStatusActions(status: string, canEdit: boolean): StatusAction[] {
  if (!canEdit) return []
  return TRANSITIONS[status] ?? []
}

export function feedbackStatusTagType(status: string): string {
  return (
    {
      NEW: 'warning',
      ACCEPTED: 'primary',
      REQUIREMENT_LINKED: 'primary',
      PLANNED: 'primary',
      DEVELOPING: 'primary',
      TESTING: 'warning',
      ONLINE: 'success',
      DUPLICATE: 'info',
      CANNOT_REPRODUCE: 'info',
      CLOSED: 'info',
    }[status] ?? ''
  )
}

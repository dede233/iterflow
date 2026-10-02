import type { Feedback, Requirement, VersionItem } from '@/types/domain'
import type { ConflictSummaryRow } from '@/types/revisionConflict'
import { feedbackStatusLabel, feedbackTypeLabel, feedbackUrgencyLabel } from '@/constants/feedback'
import { requirementStatusLabel, requirementTypeLabel } from '@/constants/requirement'
import { versionStatusLabel } from '@/constants/version'

export function feedbackConflictSummary(item: Feedback): ConflictSummaryRow[] {
  return [
    { label: '标题', value: item.title },
    { label: '反馈类型', value: feedbackTypeLabel[item.feedback_type] ?? item.feedback_type },
    { label: '紧急程度', value: feedbackUrgencyLabel[item.urgency] ?? item.urgency },
    { label: '状态', value: feedbackStatusLabel[item.status] ?? item.status },
    { label: '详细描述', value: item.description },
  ]
}

export function requirementConflictSummary(item: Requirement): ConflictSummaryRow[] {
  return [
    { label: '标题', value: item.title },
    { label: '需求类型', value: requirementTypeLabel[item.requirement_type] ?? item.requirement_type },
    { label: '优先级', value: item.priority },
    { label: '状态', value: requirementStatusLabel[item.status] ?? item.status },
    { label: '需求描述', value: item.description },
    { label: '验收标准', value: item.acceptance_criteria ?? '-' },
  ]
}

export function versionConflictSummary(item: VersionItem): ConflictSummaryRow[] {
  return [
    { label: '版本号', value: item.version_no },
    { label: '版本名称', value: item.name },
    { label: '状态', value: versionStatusLabel[item.status] ?? item.status },
    { label: '计划上线日期', value: item.planned_release_date ?? '-' },
    { label: '版本说明', value: item.description ?? '-' },
  ]
}

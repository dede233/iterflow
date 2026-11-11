import type { LocationQuery } from 'vue-router'
import { parseListQuery } from './listQuery'
import { feedbackStatusLabel, feedbackTypeLabel, feedbackUrgencyLabel } from '@/constants/feedback'
import { versionStatusLabel } from '@/constants/version'

export type FilterChip = { key: string; label: string }

/** Chips describe the validated URL snapshot, never unsubmitted form inputs. */
export function feedbackFilterChips(query: LocationQuery, systems: { id: number; name: string }[] = [], showSystems = true): FilterChip[] {
  const applied = parseListQuery('/feedbacks', query)
  const labels: Record<string, string> = { keyword: '关键词', status: '状态', feedback_type: '类型', urgency: '紧急度', system_id: '业务系统' }
  return Object.entries(applied).flatMap(([key, value]) => {
    if (!labels[key]) return []
    const text = key === 'system_id' ? (showSystems ? systems.find(s => s.id === Number(value))?.name : undefined) || '已指定'
      : key === 'status' ? feedbackStatusLabel[value]
      : key === 'feedback_type' ? feedbackTypeLabel[value]
      : key === 'urgency' ? feedbackUrgencyLabel[value] : value
    return [{ key, label: `${labels[key]}：${text || value}` }]
  })
}

export function versionFilterChips(query: LocationQuery): FilterChip[] {
  const applied = parseListQuery('/versions', query)
  const labels: Record<string, string> = { keyword: '关键词', status: '状态', owner_id: '负责人', system_id: '业务系统' }
  const chips = Object.entries(applied).flatMap(([key, value]) => labels[key]
    ? [{ key, label: `${labels[key]}：${key.endsWith('_id') ? '已指定' : key === 'status' ? versionStatusLabel[value] || value : value}` }]
    : [])
  if (applied.planned_release_from && applied.planned_release_to) chips.push({ key: 'planned_release', label: `计划上线：${applied.planned_release_from} 至 ${applied.planned_release_to}` })
  return chips
}

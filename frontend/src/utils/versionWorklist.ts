import type { Requirement } from '@/types/domain'
export function filterVersionWorklist(items: Requirement[], filters: { keyword: string; status: string; priority: string }): Requirement[] {
  const keyword = filters.keyword.trim().toLocaleLowerCase()
  return items.filter(item => (!keyword || `${item.requirement_no} ${item.title}`.toLocaleLowerCase().includes(keyword)) && (!filters.status || item.status === filters.status) && (!filters.priority || item.priority === filters.priority))
}
export function visibleWorklistStats(items: Requirement[]) {
  const byStatus: Record<string, number> = {}
  let pending = 0
  for (const item of items) { byStatus[item.status] = (byStatus[item.status] ?? 0) + 1; if (!['DONE', 'ONLINE'].includes(item.status)) pending++ }
  return { total: items.length, pending, byStatus }
}
